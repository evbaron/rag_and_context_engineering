"""Checkpoint 7.1 model routing: the switch, the two routing nodes, and the answer-check escalation.

Fake models and graphs only; no API key and no network.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from wikipedia_retrieval_engine.wiki_agents import model_routing as mr


class FakeModel:
    def __init__(self, name: str):
        self.name = name

    def invoke(self, messages):
        return f"{self.name}:{messages}"

    def with_structured_output(self, schema, **kwargs):
        return SimpleNamespace(invoke=lambda messages: f"{self.name}:{schema}")


def review(relevant=True, needs_table=False, table_ids=(), table_names=()):
    return SimpleNamespace(relevant=relevant, needs_table_reader=needs_table,
                           relevant_table_ids=list(table_ids), relevant_table_names=list(table_names))


class SwitchTests(unittest.TestCase):
    def test_switch_follows_the_holder_at_call_time(self) -> None:
        holder = mr.RouteHolder()
        switch = mr.TierSwitchModel(FakeModel("mini"), FakeModel("big"), holder)
        structured = switch.with_structured_output("Plan")  # built while cheap
        self.assertEqual(switch.invoke("q"), "mini:q")
        holder.tier = mr.STRONG
        self.assertEqual(switch.invoke("q"), "big:q")
        self.assertEqual(switch.with_structured_output("Plan").invoke([]), "big:Plan")
        self.assertEqual(structured.invoke([]), "mini:Plan")  # a runnable built earlier keeps its model
        self.assertEqual(switch.name, "big")  # other attributes come from the current model


class RouteNodeTests(unittest.TestCase):
    def test_table_flag_matches_the_results_csv_definition(self) -> None:
        self.assertTrue(mr.tables_flagged({"article_reviews": [review(needs_table=True)]}))
        self.assertTrue(mr.tables_flagged({"article_reviews": [review(table_ids=["t1"])]}))
        self.assertFalse(mr.tables_flagged({"article_reviews": [review(relevant=False, needs_table=True)]}))
        self.assertFalse(mr.tables_flagged({"article_reviews": [review()]}))

    def test_type_route(self) -> None:
        holder = mr.RouteHolder()
        node = mr.make_type_route(holder)
        result = node({"article_reviews": [review(needs_table=True)]})
        self.assertEqual((holder.tier, result["routing"]["route"]), (mr.STRONG, mr.STRONG))
        result = node({"article_reviews": [review()]})
        self.assertEqual((holder.tier, result["routing"]["route"]), (mr.CHEAP, mr.CHEAP))

    def test_size_route_sends_only_large_text_questions_to_strong(self) -> None:
        holder = mr.RouteHolder()
        texts = {"Big": "x" * 90_000, "Small": "x" * 1_000}
        node = mr.make_size_route(holder, texts.get, max_chars=80_000)
        self.assertEqual(node({"article_reviews": [review()], "selected_articles": ["Big"]})["routing"]["route"], mr.STRONG)
        self.assertEqual(node({"article_reviews": [review()], "selected_articles": ["Small"]})["routing"]["route"], mr.CHEAP)
        table = node({"article_reviews": [review(needs_table=True)], "selected_articles": ["Big"]})
        self.assertEqual((holder.tier, table["routing"]["route"]), (mr.CHEAP, mr.CHEAP))


class FakeGraph:
    def __init__(self, name: str, state: dict):
        self.name, self.state, self.calls = name, state, 0

    def invoke(self, state, config=None, **kwargs):
        self.calls += 1
        return {**self.state, "question": state["question"]}


class EscalationTests(unittest.TestCase):
    def make(self, first_state: dict, check: dict | None = None, max_chars: int = 80_000):
        holder = mr.RouteHolder()
        first = FakeGraph("first", first_state)
        strong = FakeGraph("strong", {"answer": "strong answer"})
        checked: list[tuple] = []

        def checker(question, answer, evidence):
            checked.append((question, answer, evidence))
            return check or {"check_status": "ok", "check_p_complete": 0.9, "router_cost_usd": 0.00002, "router_latency_s": 0.3}

        graph = mr.EscalatingGraph(first, strong, holder, checker, threshold=0.5, max_chars=max_chars)
        return graph, first, strong, checked

    def test_complete_answer_stays_on_mini(self) -> None:
        graph, first, strong, checked = self.make({"answer": "a", "answer_context": "ctx", "routing": mr.routing_record(route="cheap")})
        result = graph.invoke({"question": "Q"})
        self.assertEqual((first.calls, strong.calls), (1, 0))
        self.assertFalse(result["routing"]["escalated"])
        self.assertEqual(checked, [("Q", "a", "ctx")])

    def test_the_check_reads_the_draft_not_the_labelled_answer(self) -> None:
        graph, _, _, checked = self.make({"answer": "[QUARANTINED] ...\n\ndraft", "answer_drafted": "draft",
                                          "answer_context": "ctx", "routing": mr.routing_record(route="cheap")})
        graph.invoke({"question": "Q"})
        self.assertEqual(checked[0][1], "draft")

    def test_incomplete_answer_is_answered_again_on_the_strong_graph(self) -> None:
        graph, first, strong, _ = self.make({"answer": "a", "answer_context": "ctx", "routing": mr.routing_record(route="cheap")},
                                            check={"check_status": "ok", "check_p_complete": 0.2})
        result = graph.invoke({"question": "Q"})
        self.assertEqual((first.calls, strong.calls), (1, 1))
        self.assertEqual(result["answer"], "strong answer")
        self.assertEqual((result["routing"]["route"], result["routing"]["escalated"]), ("escalated", True))
        self.assertEqual(result["routing"]["check_p_complete"], 0.2)

    def test_failed_or_oversized_checks_escalate(self) -> None:
        graph, _, strong, _ = self.make({"answer": "a", "answer_context": "ctx", "routing": mr.routing_record(route="cheap")},
                                        check={"check_status": "http_400"})
        graph.invoke({"question": "Q"})
        self.assertEqual(strong.calls, 1)
        graph, _, strong, checked = self.make({"answer": "a", "answer_context": "x" * 100, "routing": mr.routing_record(route="cheap")},
                                              max_chars=50)
        result = graph.invoke({"question": "Q"})
        self.assertEqual((strong.calls, checked), (1, []))
        self.assertEqual(result["routing"]["check_status"], "evidence too large for Jev")

    def test_already_strong_after_review_is_not_checked(self) -> None:
        graph, first, strong, checked = self.make({"answer": "a", "answer_context": "ctx", "routing": mr.routing_record(route="strong")})
        result = graph.invoke({"question": "Q"})
        self.assertEqual((first.calls, strong.calls, checked), (1, 0, []))
        self.assertEqual(result["routing"]["route"], "strong")

    def test_every_path_writes_the_same_columns(self) -> None:
        """One results CSV holds rows from every path; a missing column fails the whole write."""

        holder = mr.RouteHolder()
        records = [
            mr.make_type_route(holder)({"article_reviews": [review(needs_table=True)]})["routing"],
            mr.make_type_route(holder)({"article_reviews": [review()]})["routing"],
            mr.make_size_route(holder, {"A": "x" * 10}.get)({"article_reviews": [review(needs_table=True)]})["routing"],
            mr.make_size_route(holder, {"A": "x" * 10}.get, max_chars=5)({"article_reviews": [review()], "selected_articles": ["A"]})["routing"],
        ]
        cheap_routing = mr.routing_record(route="cheap")
        for first_state, check in (
            ({"answer": "a", "answer_context": "ctx", "routing": cheap_routing}, None),
            ({"answer": "a", "answer_context": "ctx", "routing": cheap_routing}, {"check_status": "ok", "check_p_complete": 0.1}),
            ({"answer": "a", "answer_context": "x" * 100, "routing": cheap_routing}, None),
            ({"answer": "a", "answer_context": "ctx", "routing": mr.routing_record(route="strong")}, None),
        ):
            graph, _, _, _ = self.make(first_state, check, max_chars=50 if len(first_state["answer_context"]) > 50 else 80_000)
            records.append(graph.invoke({"question": "Q"})["routing"])
        for record in records:
            self.assertEqual(list(record), list(mr.ROUTING_FIELDS))

    def test_routed_graph_resets_the_tier_per_question(self) -> None:
        holder = mr.RouteHolder(tier=mr.STRONG)
        mr.RoutedGraph(FakeGraph("g", {}), holder).invoke({"question": "Q"})
        self.assertEqual(holder.tier, mr.CHEAP)


if __name__ == "__main__":
    unittest.main()
