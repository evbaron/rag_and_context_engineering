# Ordinal number

This article is about the mathematical concept. For number words denoting a position in a sequence ("first", "second", "third", etc.), see [Ordinal numeral](/wiki/Ordinal_numeral).

Representation of the ordinal numbers up to

ω

ω
{\displaystyle \omega ^{\omega }}
. One turn of the spiral corresponds to the mapping ⁠

f
(
α
)
=
ω
(
1
+
α
)
{\displaystyle f(\alpha )=\omega (1+\alpha )}
⁠. Since

f
{\displaystyle f}
 has

ω

ω
{\displaystyle \omega ^{\omega }}
 as the least fixed point, larger ordinal numbers cannot be represented on this diagram.

In [set theory](/wiki/Set_theory), an **ordinal number**, or **ordinal**, is a generalization of [ordinal numerals](/wiki/Ordinal_numeral) (first, second, nth, etc.) aimed to extend [enumeration](/wiki/Enumeration) to [infinite sets](/wiki/Infinite_set). Usually [Greek letters](/wiki/Greek_letter) are used for ordinal number [variables](/wiki/Variable_(mathematics)) to help distinguish them from [natural number](/wiki/Natural_number) variables.

A finite set can be enumerated by successively labeling each element with the least [natural number](/wiki/Natural_number) that has not been previously used. To extend this process to various [infinite sets](/wiki/Infinite_set), ordinal numbers are defined more generally as a [linearly ordered](/wiki/Linearly_ordered) class of numbers that include the natural numbers and have the property that every non-empty collection ([set](/wiki/Set_(mathematics)) or [proper class](/wiki/Proper_class)) of ordinals has a [least or "smallest" element](/wiki/Greatest_element_and_least_element) (this is needed for giving a meaning to "the least unused element"). This more general definition allows us to define an ordinal number

ω
{\displaystyle \omega }
 (omega) to be the least element that is greater than every natural number, along with ordinal numbers ⁠

ω
+
1
{\displaystyle \omega +1}
⁠, ⁠

ω
+
2
{\displaystyle \omega +2}
⁠, etc., which are even greater than ⁠

ω
{\displaystyle \omega }
⁠.

The [Zermelo–Fraenkel set theory](/wiki/Zermelo%E2%80%93Fraenkel_set_theory) asserts that, for *any* set of ordinals, there exists another ordinal greater than all of them. The answer to the question "What if that set is the set of all ordinals?" (the [Burali-Forti paradox](/wiki/Burali-Forti_paradox)) is that the collection of all ordinals is not a set, but a proper class.

A linear order such that every non-empty subset has a least element is called a [well-order](/wiki/Well-order). The [axiom of choice](/wiki/Axiom_of_choice) implies that every set can be well-ordered. Given two well-ordered sets, one is [isomorphic](/wiki/Isomorphic) to an [initial segment](/wiki/Initial_segment) of the other, and the isomorphism is unique. This allows a unique ordinal to be associated with each well-ordered set, known as its [order type](/wiki/Order_type).

Ordinal numbers are distinct from [cardinal numbers](/wiki/Cardinal_number), which measure the size of sets. Although the distinction between ordinals and cardinals is not this apparent on finite sets (one can go from one to the other just by counting labels), they are very different in the infinite case, where different infinite ordinals can correspond to sets having the same cardinal. Like other kinds of numbers, ordinals can be [added, multiplied, and exponentiated](/wiki/Ordinal_arithmetic), although none of these operations are [commutative](/wiki/Commutative_property).

Ordinals were introduced by [Georg Cantor](/wiki/Georg_Cantor) in 1883 to accommodate infinite sequences and classify [derived sets](/wiki/Derived_set_(mathematics)), which he had previously introduced in 1872 while studying the uniqueness of [trigonometric series](/wiki/Trigonometric_series).

## Motivation

A [natural number](/wiki/Natural_number) (which, in this context, includes the number [0](/wiki/0_(number))) can be used for two purposes: to describe the *size* of a [set](/wiki/Set_(mathematics)), or to describe the *position* of an element in a [sequence](/wiki/Sequence). When generalized to infinite sets, the notion of size leads to [cardinal numbers](/wiki/Cardinal_number), and the notion of position leads to the ordinal numbers described here.

In a broader mathematical sense, counting can be viewed as the instantiation of [mathematical induction](/wiki/Mathematical_induction). To enumerate a well-ordered set is effectively to verify a property for its elements sequentially. For the natural numbers, this is standard induction: if a property holds for 0, and its truth for ⁠

n
{\displaystyle n}
⁠ implies its truth for ⁠

n
+
1
{\displaystyle n+1}
⁠, then it holds for all natural numbers. This process corresponds to the first infinite ordinal, ⁠

ω
{\displaystyle \omega }
⁠.

A graphical "matchstick" representation of the ordinal ω2. Each stick corresponds to an ordinal of the form ω · *j* + *i* where j and i are natural numbers. This structure corresponds to **nested induction**: an inner induction on i and an outer induction on j.

Mathematical contexts often require iterating beyond a single infinite limit. The ordinal ⁠

ω

2
{\displaystyle \omega ^{2}}
⁠ (represented in the figure) exemplifies the concept of **nested induction**. It consists of a sequence of distinct copies of the natural numbers ordered one after another. To verify a property for all ordinals less than ⁠

ω

2
{\displaystyle \omega ^{2}}
⁠, one performs an "inner" induction (counting through ⁠

0
,
1
,
2
,
…
{\displaystyle 0,1,2,\dots }
⁠), establishes the limit at ⁠

ω
{\displaystyle \omega }
⁠, and then proceeds to the next sequence (⁠

ω
+
1
,
ω
+
2
,
…
{\displaystyle \omega +1,\omega +2,\dots }
⁠). This structure parallels a nested loop in computer programming (e.g., iterating through pairs of natural numbers ⁠

(
j
,
i
)
{\displaystyle (j,i)}
⁠ ordered [lexicographically](/wiki/Lexicographical_order)). Ordinals allow the definition of processes of arbitrary complexity, such as ⁠

ω

3
{\displaystyle \omega ^{3}}
⁠ (triple nesting) or ⁠

ω

ω
{\displaystyle \omega ^{\omega }}
⁠ (induction over the depth of nested induction).

The validity of inductive counting rests on the property of [well-foundedness](/wiki/Well-founded_relation), specifically the requirement that every process can be traced back to a "foundational" element. A linear order that exhibits this well-foundedness is termed a [well-order](/wiki/Well-order). The existence of a "least" or minimal element in every non-empty subset of a well-ordered set grounds the principle of [transfinite induction](/wiki/Transfinite_induction), generalizing standard induction by ensuring that if a property fails to hold, there exists a specific least counterexample.

Ordinals serve as the canonical abstractions of these well-ordered structures. A fundamental theorem in set theory establishes that any two well-ordered sets are [comparable](/wiki/Comparability): given two well-orders, either they are [isomorphic](/wiki/Isomorphism), or one is isomorphic to a proper [initial segment](/wiki/Initial_segment) of the other. This uniqueness implies that well-orders can be classified by their structure alone, independent of specific representations. Consequently, **ordinal numbers** are defined as the representative forms of these isomorphism classes.

## Definitions

### Well-ordering

The construction procedure of transfinite sequences implies that the ordinals used to label their elements are [well-ordered](/wiki/Well-order). This means that:

:   Every non-empty collection of ordinals ⁠

    T
    {\displaystyle T}
    ⁠ has a unique least element.

Intuitively, the least ordinal in ⁠

T
{\displaystyle T}
⁠ is the "next" ordinal introduced after all ordinals strictly less than every ordinal in ⁠

T
{\displaystyle T}
⁠ have been used. In contrast, ⁠

T
{\displaystyle T}
⁠ need not have a greatest element, for example when ⁠

T
{\displaystyle T}
⁠ is the set of all natural numbers.

Being well-ordered is stronger than merely being [linearly ordered](/wiki/Linearly_ordered). For example, the [real numbers](/wiki/Real_number) are naturally linearly ordered, but any [open interval](/wiki/Open_interval) has no least element.

The importance of well-ordering is that it enables [transfinite induction](/wiki/Transfinite_induction). If a statement ⁠

P
(
α
)
{\displaystyle P(\alpha )}
⁠ about an ordinal ⁠

α
{\displaystyle \alpha }
⁠ is not universally true for all ⁠

α
{\displaystyle \alpha }
⁠, i.e., if it has any counterexamples, then it must have a least counterexample. Conversely, if it can be proven that ⁠

P
(
α
)
{\displaystyle P(\alpha )}
⁠ is true whenever ⁠

P
(
β
)
{\displaystyle P(\beta )}
⁠ is true for all ⁠

β
<
α
{\displaystyle \beta <\alpha }
⁠, then it cannot have any least counterexample, and thus it cannot have any counterexample at all, i.e., it is indeed universally true.

### Well-ordered sets

In the usual [Zermelo–Fraenkel](/wiki/Zermelo%E2%80%93Fraenkel_set_theory) (ZF) formalization of set theory, a well-ordered set is a [totally ordered set](/wiki/Totally_ordered_set) ⁠

(
S
,
≤
)
{\displaystyle (S,\leq )}
⁠ such that every non-empty subset ⁠

T
⊆
S
{\displaystyle T\subseteq S}
⁠ has a least element. Here “set” means a collection that is itself an object of ZF, as opposed to a [proper class](/wiki/Proper_class).

A well-ordered set can be written as a transfinite sequence by assigning ordinal labels to its elements in a way that respects ordering: ⁠

a

α
≤

a

β
{\displaystyle a\_{\alpha }\leq a\_{\beta }}
⁠ if and only if ⁠

α
≤
β
{\displaystyle \alpha \leq \beta }
⁠. (Such a one-to-one correspondence between two ordered sets is called an [order isomorphism](/wiki/Order_isomorphism).) The labels used in such an enumeration form an [initial segment](/wiki/Initial_segment) of the ordinals, in the sense that if a label is used then every smaller ordinal label is also used. By well-orderedness, there is a unique least ordinal that is not used as a label; this ordinal determines the "length" of the sequence, and is called the [order type](/wiki/Order_type) of the well-ordering. Thanks to [0-based indexing](/wiki/0-based_indexing), the order type coincides with the [cardinality](/wiki/Cardinality) for finite sets, including the empty set. However, for infinite sets, different well-order relations ⁠

≤
{\displaystyle \leq }
⁠ can have different order types.

### Definition of an ordinal as an equivalence class

Order types can be defined without a preexisting notion of ordinals, by working directly with order isomorphisms between general well-ordered sets, just as [cardinality](/wiki/Cardinality) can be defined through [bijections](/wiki/Bijections) between general (unordered) sets. As with bijections, being order-isomorphic is an [equivalence relation](/wiki/Equivalence_relation) on well-ordered sets; its [equivalence classes](/wiki/Equivalence_class) correspond to order types (ordinals).

In the *[Principia Mathematica](/wiki/Principia_Mathematica)* approach, the order type of a well-ordered set ⁠

(
S
,
≤
)
{\displaystyle (S,\leq )}
⁠ is *identified with* its [isomorphism class](/wiki/Isomorphism_class), i.e., the set of all well-ordered sets ⁠

(

S
′
,

≤
′
)
{\displaystyle (S',\leq ')}
⁠ order-isomorphic to ⁠

(
S
,
≤
)
{\displaystyle (S,\leq )}
⁠. Since elements of ⁠

S
′
{\displaystyle S'}
⁠ are allowed to be *anything*, this definition has the “[set of all sets](/wiki/Set_of_all_sets)” flavor, and in ZF such collections are generally too large to be sets. This definition can still be used in [type theory](/wiki/Type_theory) and in Quine's axiomatic set theory [New Foundations](/wiki/New_Foundations) and related systems.

In [ZF](/wiki/Zermelo%E2%80%93Fraenkel_set_theory) and related systems of [axiomatic set theory](/wiki/Axiomatic_set_theory), these equivalence classes are generally too large to form sets. Consequently, it is necessary to select a unique, canonical representative from each class—a single set that embodies the structure of the well-ordering. Since the fundamental relation in set theory is set membership (⁠

∈
{\displaystyle \in }
⁠), the ideal representation is one where the abstract order relation ⁠

<
{\displaystyle <}
⁠ is translated directly into the membership relation ⁠

∈
{\displaystyle \in }
⁠.

## Von Neumann definition of ordinals

The **von Neumann representation** provides this canonical form. It relies on the observation that any [well-founded relation](/wiki/Well-founded_relation) satisfying certain properties can be mapped to a specific set where the relation becomes set membership. This mapping is known as the [Mostowski collapse lemma](/wiki/Mostowski_collapse_lemma).

When applied to a well-ordering, the Mostowski collapse yields a specific set ⁠

S
{\displaystyle S}
⁠ where the order relation ⁠

x
<
y
{\displaystyle x<y}
⁠ is true if and only if ⁠

x
∈
y
{\displaystyle x\in y}
⁠. The resulting sets have the property that they are [transitive](/wiki/Transitive_set): every element of ⁠

S
{\displaystyle S}
⁠ is also a subset of ⁠

S
{\displaystyle S}
⁠ (i.e., the union of the set is contained within the set). In this representation, each ordinal is identified with the set of all preceding ordinals.

Thus the finite **von Neumann ordinals** are defined [recursively](/wiki/Recursively) as ⁠

0
=
∅
{\displaystyle 0=\emptyset }
⁠, ⁠

1
=
{
0
}
{\displaystyle 1=\{0\}}
⁠, ⁠

2
=
{
0
,
1
}
{\displaystyle 2=\{0,1\}}
⁠, etc. The first infinite ordinal ⁠

ω
{\displaystyle \omega }
⁠ is represented by the set of all finite ordinals, i.e., the set of [von Neumann natural numbers](/wiki/Von_Neumann_natural_number) ⁠

N
=
{
0
,
1
,
2
,
…
}
{\displaystyle \mathbb {N} =\{0,1,2,\ldots \}}
⁠. Then ⁠

ω
+
1
=
{
0
,
1
,
2
,
…
,
ω
}
=

N
∪
{
ω
}
{\displaystyle \omega +1=\{0,1,2,\ldots ,\omega \}=\mathbb {N} \cup \{\omega \}}
⁠, and so on.

Informally, one may define an ordinal recursively as a [downward closed](/wiki/Downward_closed) set of ordinals. Such a recursive definition is usually justified with the [transitive closure](/wiki/Transitive_set#Transitive_closure). However, the von Neumann ordinals are already [transitive sets](/wiki/Transitive_set), allowing them to be formally defined by a concise statement:

:   A set

    S
    {\displaystyle S}
     is an ordinal if and only if

    S
    {\displaystyle S}
     is [transitive](/wiki/Transitive_set) (every element of

    S
    {\displaystyle S}
     is a subset of

    S
    {\displaystyle S}
    ) and strictly well-ordered by set membership (

    ∈
    {\displaystyle \in }
    ).

The set ⁠

ω
≡

N
{\displaystyle \omega \equiv \mathbb {N} }
⁠ is usually defined as the smallest inductive set (containing ⁠

∅
{\displaystyle \emptyset }
⁠ and closed under successor). The "smallest" constraint guarantees that each element of ⁠

ω
{\displaystyle \omega }
⁠ is either zero or the successor of another element of ⁠

ω
{\displaystyle \omega }
⁠, which allows induction to demonstrate that ⁠

ω
{\displaystyle \omega }
⁠ indeed satisfies the formal definition of ordinals stated above.

### Basic properties

Defining the strict order relation ⁠

<
{\displaystyle <}
⁠ as the membership relation ⁠

∈
{\displaystyle \in }
⁠ restricted to the class of all ordinals, the recursive characterization ⁠

γ
=
{
α
∣
α
<
γ
}
{\displaystyle \gamma =\{\alpha \mid \alpha <\gamma \}}
⁠ is reduced to the following statement:

- *If ⁠

  α
  ∈
  β
  {\displaystyle \alpha \in \beta }
  ⁠ and ⁠

  β
  {\displaystyle \beta }
  ⁠ is an ordinal, then ⁠

  α
  {\displaystyle \alpha }
  ⁠ is an ordinal*: transitivity of ⁠

  α
  {\displaystyle \alpha }
  ⁠ as a set is found by finding that all the relevant ordinals are elements of ⁠

  β
  {\displaystyle \beta }
  ⁠ and then using the transitivity of the ⁠

  ∈
  {\displaystyle \in }
  ⁠ relation within ⁠

  β
  {\displaystyle \beta }
  ⁠; well-orderedness of ⁠

  α
  {\displaystyle \alpha }
  ⁠ follows straightforwardly from well-orderedness of ⁠

  β
  {\displaystyle \beta }
  ⁠.

The non-strict order relation ⁠

≤
{\displaystyle \leq }
⁠ has an alternative characterization: ⁠

α
≤
β
{\displaystyle \alpha \leq \beta }
⁠ if and only if ⁠

α
⊆
β
{\displaystyle \alpha \subseteq \beta }
⁠ for ordinals ⁠

α
,
β
{\displaystyle \alpha ,\beta }
⁠. The "if" direction follows from transitivity of ⁠

β
{\displaystyle \beta }
⁠, and the "only if" direction follows from:

- *If ⁠

  α
  ≠
  β
  {\displaystyle \alpha \neq \beta }
  ⁠ are both ordinals and ⁠

  α
  ⊂
  β
  {\displaystyle \alpha \subset \beta }
  ⁠, then ⁠

  α
  ∈
  β
  {\displaystyle \alpha \in \beta }
  ⁠*: let ⁠

  γ
  =
  min
  {
  β
  ∖
  α
  }
  {\displaystyle \gamma =\min\{\beta \setminus \alpha \}}
  ⁠. ⁠

  α
  {\displaystyle \alpha }
  ⁠ is transitive so ⁠

  α
  =
  {
  ξ
  ∈
  β
  ∣
  ξ
  <
  γ
  }
  =
  γ
  ∈
  β
  {\displaystyle \alpha =\{\xi \in \beta \mid \xi <\gamma \}=\gamma \in \beta }
  ⁠.

This implies that ⁠

≤
{\displaystyle \leq }
⁠ is a [partial order](/wiki/Partial_order). It is in fact a [total order](/wiki/Total_order), and a [well-order](/wiki/Well-order):

- *If ⁠

  α
  {\displaystyle \alpha }
  ⁠ and ⁠

  β
  {\displaystyle \beta }
  ⁠ are both ordinals, then ⁠

  α
  ⊆
  β
  {\displaystyle \alpha \subseteq \beta }
  ⁠ or ⁠

  β
  ⊆
  α
  {\displaystyle \beta \subseteq \alpha }
  ⁠*: ⁠

  γ
  =
  α
  ∩
  β
  {\displaystyle \gamma =\alpha \cap \beta }
  ⁠ is an ordinal, so ⁠

  γ
  =
  α
  {\displaystyle \gamma =\alpha }
  ⁠ or ⁠

  γ
  =
  β
  {\displaystyle \gamma =\beta }
  ⁠, or else ⁠

  γ
  ∈
  γ
  {\displaystyle \gamma \in \gamma }
  ⁠, contradicting irreflexivity.
- If ⁠

  A
  {\displaystyle A}
  ⁠ is a nonempty set of ordinals, then ⁠

  min
  A
  =
  ⋂
  A
  {\displaystyle \min A=\bigcap A}
  ⁠ must be in ⁠

  A
  {\displaystyle A}
  ⁠ by similar logic.

So all ordinal numbers form a well-ordered class ⁠

O
N
{\displaystyle \mathrm {ON} }
⁠, and thus any nonempty set of ordinals equipped with ⁠

≤
{\displaystyle \leq }
⁠ is a well-ordered set.

Specific ordinals can be constructed explicitly with the following principles:

- ⁠

  0
  =
  ∅
  {\displaystyle 0=\emptyset }
  ⁠ is an ordinal.
- For any ordinal ⁠

  α
  {\displaystyle \alpha }
  ⁠, ⁠

  s
  u
  c
  c

  α
  =
  α
  ∪
  {
  α
  }
  {\displaystyle \mathrm {succ} \;\alpha =\alpha \cup \{\alpha \}}
  ⁠ is an ordinal and ⁠

  s
  u
  c
  c

  α
  =
  min
  {
  β
  ∣
  β
  >
  α
  }
  {\displaystyle \mathrm {succ} \;\alpha =\min\{\beta \mid \beta >\alpha \}}
  ⁠.
- If A is a set of ordinals, then

  sup
  A
  =
  ⋃
  A
  {\displaystyle \sup A=\bigcup A}
   is an ordinal.

The explicit forms of ⁠

s
u
c
c
{\displaystyle \mathrm {succ} }
⁠ and ⁠

sup
{\displaystyle \sup }
⁠ imply that for any set of ordinals, there exists another ordinal greater than all of them. In other words,

- ([Burali-Forti paradox](/wiki/Burali-Forti_paradox)) The class of all ordinals ⁠

  O
  N
  {\displaystyle \mathrm {ON} }
  ⁠ is not a set; otherwise ⁠

  s
  u
  c
  c
  sup

  O
  N
  {\displaystyle \mathrm {succ} \sup \mathrm {ON} }
  ⁠ would be an ordinal not in ⁠

  O
  N
  {\displaystyle \mathrm {ON} }
  ⁠.

### Order types

Every well-ordered set

S
{\displaystyle S}
 is order-isomorphic to exactly one ordinal, known as its *[order type](/wiki/Order_type)*. Uniqueness is guaranteed because a well-ordered set cannot be isomorphic to a proper initial segment of itself, preventing isomorphism to two distinct ordinals. The existence of this ordinal is proven by defining a map pairing each

x
∈
S
{\displaystyle x\in S}
 with the ordinal representing the order type of the initial segment ⁠

S

x
=
{
y
∈
S
∣
y
<
x
}
{\displaystyle S\_{x}=\{y\in S\mid y<x\}}
⁠. By the [Axiom schema of replacement](/wiki/Axiom_schema_of_replacement), the range of this map is a set of ordinals. Because this range is downward closed (the order type of a segment of a segment is a smaller ordinal), the range is itself an ordinal

γ
{\displaystyle \gamma }
. The domain of the isomorphism must be all of

S
{\displaystyle S}
; otherwise, the least element

z
∈
S
{\displaystyle z\in S}
 outside the domain would imply

S

z
≅
γ
{\displaystyle S\_{z}\cong \gamma }
, which would effectively include

z
{\displaystyle z}
 in the domain, a contradiction. Thus,

S
≅
γ
{\displaystyle S\cong \gamma }
.

## Successor and limit ordinals

Every ordinal number is one of three types: the ordinal zero, a successor ordinal, or a limit ordinal.

- *[Zero](/wiki/Zero)*: The ordinal

  0
  =
  ∅
  {\displaystyle 0=\emptyset }
   is the least ordinal.
- *[Successor ordinals](/wiki/Successor_ordinal)*: An ordinal

  α
  {\displaystyle \alpha }
   is a successor if

  α
  =
  S
  (
  β
  )
  =
  β
  ∪
  {
  β
  }
  {\displaystyle \alpha =S(\beta )=\beta \cup \{\beta \}}
   for some ordinal

  β
  {\displaystyle \beta }
  . In this case,

  β
  {\displaystyle \beta }
   is the maximum element of

  α
  {\displaystyle \alpha }
  .
- *[Limit ordinals](/wiki/Limit_ordinals)*: An ordinal

  λ
  {\displaystyle \lambda }
   is a limit ordinal if

  λ
  ≠
  0
  {\displaystyle \lambda \neq 0}
   and

  λ
  {\displaystyle \lambda }
   is not a successor ordinal.

There is variation in the definition of limit ordinals regarding the inclusion of zero. Some texts, such as *Introduction to Cardinal Arithmetic* by Holz et al., define a limit ordinal as a non-zero ordinal that is not a successor. In contrast, other standard set theory texts, including Jech's *Set Theory* and Just and Weese's *Discovering Modern Set Theory*, define a limit ordinal simply as any ordinal that is not a successor, which implies that 0 is a limit ordinal. When the topological definition is used (based on the [order topology](/wiki/Order_topology)), 0 is not a limit ordinal because it is not a [limit point](/wiki/Limit_point) of the set of smaller ordinals (which is empty); Rosenstein's *Linear Orderings* uses this definition. When 0 is included as a limit, ordinals that are strictly greater than 0 and not successors are usually referred to as "nonzero limit ordinals".

The following properties characterize nonzero limit ordinals:

:   λ
    {\displaystyle \lambda }
     is a nonzero limit ordinal if and only if

    λ
    ≠
    0
    {\displaystyle \lambda \neq 0}
     and for every ordinal

    α
    <
    λ
    {\displaystyle \alpha <\lambda }
    , the successor

    S
    (
    α
    )
    {\displaystyle S(\alpha )}
     is also less than

    λ
    {\displaystyle \lambda }
    .

This implies that a nonzero limit ordinal is equal to the supremum of all ordinals strictly less than it:

:   λ
    {\displaystyle \lambda }
     is a nonzero limit ordinal if and only if

    λ
    =
    sup
    {
    α
    ∣
    α
    <
    λ
    }
    =
    ⋃
    λ
    {\displaystyle \lambda =\sup\{\alpha \mid \alpha <\lambda \}=\bigcup \lambda }
     and

    λ
    ≠
    0
    {\displaystyle \lambda \neq 0}
    .

For example,

ω
{\displaystyle \omega }
 is a limit ordinal because any natural number is less than ⁠

ω
{\displaystyle \omega }
⁠, and the successor of any natural number is also a natural number (hence less than ⁠

ω
{\displaystyle \omega }
⁠). It is the least limit ordinal because each natural number ⁠

n
∈
ω
{\displaystyle n\in \omega }
⁠ is either zero or a successor.

## Termination of decreasing sequences

Any strictly decreasing sequence of ordinals ⁠

α

0
>

α

1
>

α

2
>
⋯
{\displaystyle \alpha \_{0}>\alpha \_{1}>\alpha \_{2}>\cdots }
⁠ must be finite. This follows directly from the natural ordering of ordinals being a well-order: if there existed such an infinite decreasing sequence, then the set ⁠

{

α

i
∣
i
∈

N
}
{\displaystyle \{\alpha \_{i}\mid i\in \mathbb {N} \}}
⁠ would be a set of ordinals without a least element. By the same argument, a well-ordered set has no infinite strictly descending chains; in fact, assuming the [axiom of dependent choice](/wiki/Axiom_of_dependent_choice), any [total order](/wiki/Total_order) that satisfies this condition is a well-order, giving an alternative characterization of well-ordered sets. The fact this is true for natural numbers is the basis of Fermat's method of [proof by infinite descent](/wiki/Proof_by_infinite_descent), which can be generalized to ordinals and other well-ordered classes too, as a special case of [transfinite induction](/wiki/Transfinite_induction) where the proof of any ⁠

P
(
α
)
{\displaystyle P(\alpha )}
⁠ only requires ⁠

P
(
β
)
{\displaystyle P(\beta )}
⁠ for at most one specific ⁠

β
<
α
{\displaystyle \beta <\alpha }
⁠.

This property may be surprising when the initial value is an infinite ordinal. Indeed, for sequences starting from a natural number ⁠

n
{\displaystyle n}
⁠, the longest sequence is always one that decreases by 1 every step, leading to a sequence with ⁠

n
{\displaystyle n}
⁠ steps (⁠

n
+
1
{\displaystyle n+1}
⁠ elements). This strategy of descending to the immediate predecessor remains valid for successor ordinals. However, a limit ordinal ⁠

λ
{\displaystyle \lambda }
⁠ has no immediate predecessor to descend to, so any next term must jump to some ⁠

β
<
λ
{\displaystyle \beta <\lambda }
⁠, skipping infinitely many ordinals strictly between ⁠

β
{\displaystyle \beta }
⁠ and ⁠

λ
{\displaystyle \lambda }
⁠. For example, when descending from ⁠

ω
{\displaystyle \omega }
⁠, one must choose a finite natural number, and thus "commit" to the number of maximum remaining steps. Descending from ⁠

ω
⋅
k
{\displaystyle \omega \cdot k}
⁠ allows one to make such a commitment ⁠

k
{\displaystyle k}
⁠ times, and descending from ⁠

ω

2
{\displaystyle \omega ^{2}}
⁠ allows one to commit to a finite value of ⁠

k
{\displaystyle k}
⁠. Larger ordinals may allow more complicated decision structures, but the number of descending steps remains unbounded but finite.

This property is useful for proving termination for any procedure. If the states of a computation (computer program or game) can be well-ordered—in such a way that each step is followed by a "lower" step—then the computation will terminate.

## Transfinite sequence

If

α
{\displaystyle \alpha }
 is any ordinal and

X
{\displaystyle X}
 is a set, an

α
{\displaystyle \alpha }
-indexed sequence of elements of

X
{\displaystyle X}
 is a function from

α
{\displaystyle \alpha }
 to

X
{\displaystyle X}
. This concept, a **transfinite sequence** (if

α
{\displaystyle \alpha }
 is infinite) or *ordinal-indexed sequence*, is a generalization of the concept of a [sequence](/wiki/Sequence). An ordinary sequence corresponds to the case

α
=
ω
{\displaystyle \alpha =\omega }
, while a finite

α
{\displaystyle \alpha }
 corresponds to a [tuple](/wiki/Tuple_(mathematics)), a.k.a. [string](/wiki/String_(computer_science)).

While a sequence indexed by a specific ordinal

α
{\displaystyle \alpha }
 is a set, a sequence indexed by the class of all ordinals is a [proper class](/wiki/Proper_class). The [Axiom schema of replacement](/wiki/Axiom_schema_of_replacement) guarantees that any initial segment of such a class-sequence (the restriction of the function to some specific ordinal

δ
{\displaystyle \delta }
) is a set.

When

⟨

x

ι
∣
ι
<
λ
⟩
{\displaystyle \langle x\_{\iota }\mid \iota <\lambda \rangle }
 is a transfinite sequence of ordinals indexed by a limit ordinal

λ
{\displaystyle \lambda }
 and the sequence is *increasing* (i.e.

ι
<
ρ

⟹

x

ι
<

x

ρ
{\displaystyle \iota <\rho \implies x\_{\iota }<x\_{\rho }}
), its *limit* is defined as the least upper bound of the set

{

x

ι
∣
ι
<
λ
}
{\displaystyle \{x\_{\iota }\mid \iota <\lambda \}}
.

A transfinite sequence

f
{\displaystyle f}
 mapping ordinals to ordinals is said to be *[continuous](/wiki/Continuous_function_(set_theory))* (in the order topology) if for every limit ordinal

λ
{\displaystyle \lambda }
 in its domain,

- if *f* (λ) is a limit ordinal and for every ε < *f* (λ) there exists a δ < λ such that for every γ, if δ < γ < λ, then ε < *f* (γ) ≤ *f* (λ), and
- if *f* (λ) is *not* a limit ordinal, there exists a δ < λ such that for every γ, if δ < γ < λ, then *f* (γ) = *f* (λ).

A sequence is called **normal** if it is both strictly increasing and continuous. If a sequence *f* is increasing (not necessarily strictly) and continuous and λ is a limit ordinal, then

f
(
λ
)
=

⋃

β
<
λ
f
(
β
)
{\displaystyle f(\lambda )=\bigcup \_{\beta <\lambda }f(\beta )}
.

## Transfinite induction

Main article: [Transfinite induction](/wiki/Transfinite_induction)

Transfinite induction holds in any [well-ordered](/wiki/Well-order) set, but it is so important in relation to ordinals that it is worth restating here.

:   Any property that passes from the set of ordinals smaller than a given ordinal α to α itself, is true of all ordinals.

That is, if *P*(α) is true whenever *P*(β) is true for all β < α, then *P*(α) is true for *all* α. Or, more practically: in order to prove a property *P* for all ordinals α, one can assume that it is already known for all smaller β < α.

### Transfinite recursion

Transfinite induction can be used not only to prove theorems but also to define functions on ordinals. This is known as *[transfinite recursion](/wiki/Transfinite_recursion)*.

Formally, a function F is defined by transfinite recursion on the ordinals if, for every ordinal α, the value ⁠

F
(
α
)
{\displaystyle F(\alpha )}
⁠ is specified using the set of values

{
F
(
β
)
∣
β
<
α
}
{\displaystyle \{F(\beta )\mid \beta <\alpha \}}
.

Very often, when defining a function *F* by transfinite recursion on all ordinals, the definition is separated into cases based on the type of the ordinal:

1. *Base case*: Define

   F
   (
   0
   )
   {\displaystyle F(0)}
   .
2. *Successor step*: Define

   F
   (
   α
   +
   1
   )
   {\displaystyle F(\alpha +1)}
    assuming

   F
   (
   α
   )
   {\displaystyle F(\alpha )}
    is defined.
3. *Limit step*: For a limit ordinal

   λ
   {\displaystyle \lambda }
   , define

   F
   (
   λ
   )
   {\displaystyle F(\lambda )}
    as the limit of

   F
   (
   β
   )
   {\displaystyle F(\beta )}
    for all

   β
   <
   λ
   {\displaystyle \beta <\lambda }
    (either in the sense of ordinal limits or some other notion of limit if the codomain allows it).

The interesting step in the definition is usually the successor step. If

F
(
α
)
{\displaystyle F(\alpha )}
 for limit ordinals

α
{\displaystyle \alpha }
 is defined as the [limsup](/wiki/Limsup) of

F
(
β
)
{\displaystyle F(\beta )}
 for

β
<
α
{\displaystyle \beta <\alpha }
 and

F
{\displaystyle F}
 takes ordinal values and is non-decreasing, the function

F
{\displaystyle F}
 will be continuous as defined above. Ordinal addition, multiplication and exponentiation are continuous as functions of their second argument.

The existence and uniqueness of such a function are proven by constructing it as the union of partial approximations. The proof proceeds in three steps:

1. *Local Existence:* For any specific ordinal δ, one proves the existence of a unique "recursion segment"—a function defined on δ that satisfies the recursive rule for all ⁠

   β
   <
   δ
   {\displaystyle \beta <\delta }
   ⁠.
2. *Uniqueness and Compatibility:* One proves that any two recursion segments agree on their common domain. If ⁠

   g

   1
   {\displaystyle g\_{1}}
   ⁠ is a segment on ⁠

   δ

   1
   {\displaystyle \delta \_{1}}
   ⁠ and ⁠

   g

   2
   {\displaystyle g\_{2}}
   ⁠ is a segment on ⁠

   δ

   2
   {\displaystyle \delta \_{2}}
   ⁠ with ⁠

   δ

   1
   <

   δ

   2
   {\displaystyle \delta \_{1}<\delta \_{2}}
   ⁠, then ⁠

   g

   2
   {\displaystyle g\_{2}}
   ⁠ restricted to ⁠

   δ

   1
   {\displaystyle \delta \_{1}}
   ⁠ is identical to ⁠

   g

   1
   {\displaystyle g\_{1}}
   ⁠.
3. *Global Definition:* The global class function F is defined as the union of all such unique recursion segments. For any ordinal α, the value ⁠

   F
   (
   α
   )
   {\displaystyle F(\alpha )}
   ⁠ is the value assigned to α by any recursion segment defined on a domain larger than α.

The rigorous justification for local existence relies on the [axiom schema of replacement](/wiki/Axiom_schema_of_replacement) for the step of limit ordinals in order to collect the recursion segments into a set.

This construction allows definitions such as ordinal addition, multiplication, and exponentiation to be rigorous. For example, exponentiation ⁠

α

β
{\displaystyle \alpha ^{\beta }}
⁠ is defined recursively on β:

- α

  0
  =
  1
  {\displaystyle \alpha ^{0}=1}
- α

  β
  +
  1
  =

  α

  β
  ⋅
  α
  {\displaystyle \alpha ^{\beta +1}=\alpha ^{\beta }\cdot \alpha }
   (for successor ordinals)
- α

  λ
  =

  ⋃

  0
  <
  β
  <
  λ

  α

  β
  {\displaystyle \alpha ^{\lambda }=\bigcup \_{0<\beta <\lambda }\alpha ^{\beta }}
   (for limit ordinals λ)

The principle of transfinite recursion also implies that recursion can be performed up to a specific ordinal

δ
{\displaystyle \delta }
 (defining a set rather than a proper class). This is often used to define sequences of length

ω
{\displaystyle \omega }
. For example, to prove that a [normal function](#Transfinite_sequence)

f
{\displaystyle f}
 has arbitrarily large [fixed points](/wiki/Fixed_point_(mathematics)), one constructs a sequence starting with any ordinal

γ

0
{\displaystyle \gamma \_{0}}
 and defines

γ

n
+
1
=
f
(

γ

n
)
{\displaystyle \gamma \_{n+1}=f(\gamma \_{n})}
 by recursion on

n
<
ω
{\displaystyle n<\omega }
. Then the limit

δ
=

sup

n
<
ω

γ

n
{\displaystyle \delta =\sup \_{n<\omega }\gamma \_{n}}
 is a fixed point of

f
{\displaystyle f}
 because continuity ensures

f
(
δ
)
=
f
(
sup

γ

n
)
=
sup
f
(

γ

n
)
=
sup

γ

n
+
1
=
δ
{\displaystyle f(\delta )=f(\sup \gamma \_{n})=\sup f(\gamma \_{n})=\sup \gamma \_{n+1}=\delta }
.

### Indexing classes of ordinals

Any well-ordered set is similar (order-isomorphic) to a unique ordinal number

α
{\displaystyle \alpha }
; in other words, its elements can be indexed in increasing fashion by the ordinals less than ⁠

α
{\displaystyle \alpha }
⁠. This applies, in particular, to any set of ordinals: any set of ordinals is naturally indexed by the ordinals less than some ⁠

α
{\displaystyle \alpha }
⁠. The same holds, with a slight modification, for *classes* of ordinals (a collection of ordinals, possibly too large to form a set, defined by some property): any class of ordinals can be indexed by ordinals (and, when the class is unbounded in the class of all ordinals, this puts it in class-bijection with the class of all ordinals). So the

γ
{\displaystyle \gamma }
-th element in the class (with the convention that the "0-th" is the smallest, the "1-st" is the next smallest, and so on) can be freely spoken of. Formally, the definition is by transfinite induction: the

γ
{\displaystyle \gamma }
-th element of the class is defined (provided it has already been defined for all

β
<
γ
{\displaystyle \beta <\gamma }
), as the smallest element greater than the

β
{\displaystyle \beta }
-th element for all ⁠

β
<
γ
{\displaystyle \beta <\gamma }
⁠.

This could be applied, for example, to the class of limit ordinals: the

γ
{\displaystyle \gamma }
-th ordinal, which is either a limit or zero is

ω
⋅
γ
{\displaystyle \omega \cdot \gamma }
 (see [ordinal arithmetic](/wiki/Ordinal_arithmetic) for the definition of multiplication of ordinals). Similarly, one can consider *[additively indecomposable ordinals](/wiki/Additively_indecomposable_ordinal)* (meaning a nonzero ordinal that is not the sum of two strictly smaller ordinals): the

γ
{\displaystyle \gamma }
-th additively indecomposable ordinal is indexed as ⁠

ω

γ
{\displaystyle \omega ^{\gamma }}
⁠. The technique of indexing classes of ordinals is often useful in the context of fixed points: for example, the

γ
{\displaystyle \gamma }
-th ordinal

α
{\displaystyle \alpha }
 such that

ω

α
=
α
{\displaystyle \omega ^{\alpha }=\alpha }
 is written ⁠

ε

γ
{\displaystyle \varepsilon \_{\gamma }}
⁠. These are called the "[epsilon numbers](/wiki/Epsilon_numbers_(mathematics))".

## Arithmetic of ordinals

Main article: [Ordinal arithmetic](/wiki/Ordinal_arithmetic)

There are three usual operations on ordinals: addition, multiplication, and exponentiation. Each can be defined in essentially two different ways: either by constructing an explicit well-ordered set that represents the operation or by using transfinite recursion. The [Cantor normal form](/wiki/Ordinal_arithmetic#Cantor_normal_form) provides a standardized way of writing ordinals. It uniquely represents each ordinal as a finite sum of ordinal powers of ω. However, this cannot form the basis of a universal ordinal notation due to such self-referential representations as ε0 = ωε0.

Ordinals are a subclass of the class of [surreal numbers](/wiki/Surreal_number), and the so-called "natural" arithmetical operations for surreal numbers are an alternative way to combine ordinals arithmetically. They retain commutativity at the expense of continuity.

Interpreted as *[nimbers](/wiki/Nimber)*, a game-theoretic variant of numbers, ordinals can also be combined via nimber arithmetic operations. These operations are commutative but the restriction to natural numbers is generally not the same as ordinary addition of natural numbers.

## Ordinals and cardinals

### Initial ordinal of a cardinal

Each ordinal associates with one [cardinal](/wiki/Cardinal_number), its cardinality. If there is a bijection between two ordinals (e.g. ω = 1 + ω and ω + 1 > ω), then they associate with the same cardinal. Any well-ordered set having an ordinal as its order-type has the same cardinality as that ordinal. The least ordinal associated with a given cardinal is called the *initial ordinal* of that cardinal. Every finite ordinal (natural number) is initial, and no other ordinal associates with its cardinal. But most infinite ordinals are not initial, as many infinite ordinals associate with the same cardinal. The [axiom of choice](/wiki/Axiom_of_choice) is equivalent to the statement that every set can be well-ordered, i.e. that every cardinal has an initial ordinal. In theories with the axiom of choice, the cardinal number of any set has an initial ordinal, and one may employ the [Von Neumann cardinal assignment](/wiki/Von_Neumann_cardinal_assignment) as the cardinal's representation. (However, we must then be careful to distinguish between cardinal arithmetic and ordinal arithmetic.) In set theories without the axiom of choice, a cardinal may be represented by the set of sets with that cardinality having minimal rank (see [Scott's trick](/wiki/Scott%27s_trick)).

One issue with Scott's trick is that it identifies the cardinal number

0
{\displaystyle 0}
 with ⁠

{
∅
}
{\displaystyle \{\emptyset \}}
⁠, which in some formulations is the ordinal number ⁠

1
{\displaystyle 1}
⁠. It may be clearer to apply Von Neumann cardinal assignment to finite cases and to use Scott's trick for sets which are infinite or do not admit well orderings. Note that cardinal and ordinal arithmetic agree for finite numbers.

The α-th infinite initial ordinal is written ⁠

ω

α
{\displaystyle \omega \_{\alpha }}
⁠, it is always a limit ordinal. Its cardinality is written ⁠

ℵ

α
{\displaystyle \aleph \_{\alpha }}
⁠. For example, the cardinality of ω0 = ω is ⁠

ℵ

0
{\displaystyle \aleph \_{0}}
⁠, which is also the cardinality of ω2 or ε0 (all are countable ordinals). So ω can be identified with ⁠

ℵ

0
{\displaystyle \aleph \_{0}}
⁠, except that the notation

ℵ

0
{\displaystyle \aleph \_{0}}
 is used when writing cardinals, and ω when writing ordinals (this is important since, for example,

ℵ

0

2
{\displaystyle \aleph \_{0}^{2}}
 =

ℵ

0
{\displaystyle \aleph \_{0}}
 whereas

ω

2
>
ω
{\displaystyle \omega ^{2}>\omega }
). Also,

ω

1
{\displaystyle \omega \_{1}}
 is the smallest uncountable ordinal (to see that it exists, consider the set of equivalence classes of well-orderings of the natural numbers: each such well-ordering defines a countable ordinal, and

ω

1
{\displaystyle \omega \_{1}}
 is the order type of that set),

ω

2
{\displaystyle \omega \_{2}}
 is the smallest ordinal whose cardinality is greater than ⁠

ℵ

1
{\displaystyle \aleph \_{1}}
⁠, and so on, and

ω

ω
{\displaystyle \omega \_{\omega }}
 is the limit of the

ω

n
{\displaystyle \omega \_{n}}
 for natural numbers *n* (any limit of cardinals is a cardinal, so this limit is indeed the first cardinal after all the

ω

n
{\displaystyle \omega \_{n}}
).

### Cofinality

The [cofinality](/wiki/Cofinality) of an ordinal

α
{\displaystyle \alpha }
 is the smallest ordinal

δ
{\displaystyle \delta }
 that is the order type of a [cofinal](/wiki/Cofinal_(mathematics)) subset of ⁠

α
{\displaystyle \alpha }
⁠. Notice that a number of authors define cofinality or use it only for limit ordinals. The cofinality of a set of ordinals or any other well-ordered set is the cofinality of the order type of that set.

Thus for a limit ordinal, there exists a

δ
{\displaystyle \delta }
-indexed strictly increasing sequence with limit ⁠

α
{\displaystyle \alpha }
⁠. For example, the cofinality of ω2 is ω, because the sequence ω·*m* (where *m* ranges over the natural numbers) tends to ω2; but, more generally, any countable limit ordinal has cofinality ω. An uncountable limit ordinal may have either cofinality ω as does

ω

ω
{\displaystyle \omega \_{\omega }}
 or an uncountable cofinality.

The cofinality of 0 is 0. And the cofinality of any successor ordinal is 1. The cofinality of any limit ordinal is at least ⁠

ω
{\displaystyle \omega }
⁠.

An ordinal that is equal to its cofinality is called [regular](/wiki/Regular_ordinal) and it is always an initial ordinal. Any limit of regular ordinals is a limit of initial ordinals and thus is also initial even if it is not regular, which it usually is not. If the axiom of choice holds, then

ω

α
+
1
{\displaystyle \omega \_{\alpha +1}}
 is regular for each *α*. In this case, the ordinals 0, 1, ⁠

ω
{\displaystyle \omega }
⁠, ⁠

ω

1
{\displaystyle \omega \_{1}}
⁠, and

ω

2
{\displaystyle \omega \_{2}}
 are regular, whereas 2, 3, ⁠

ω

ω
{\displaystyle \omega \_{\omega }}
⁠, and ωω·2 are initial ordinals that are not regular.

The cofinality of any ordinal *α* is a regular ordinal, i.e. the cofinality of the cofinality of *α* is the same as the cofinality of *α*. So the cofinality operation is [idempotent](/wiki/Idempotent).

### Closed unbounded sets and classes

The concepts of closed and unbounded sets are typically formulated for subsets of a [regular cardinal](/wiki/Regular_cardinal)

κ
{\displaystyle \kappa }
 that is uncountable. A subset

C
⊆
κ
{\displaystyle C\subseteq \kappa }
 is said to be *unbounded* (or cofinal) in

κ
{\displaystyle \kappa }
 if for every ordinal

α
<
κ
{\displaystyle \alpha <\kappa }
, there exists some

β
∈
C
{\displaystyle \beta \in C}
 such that

α
<
β
{\displaystyle \alpha <\beta }
. To define the property of being closed, one first defines a limit point: a non-zero ordinal

δ
<
κ
{\displaystyle \delta <\kappa }
 is a limit point of

C
{\displaystyle C}
 if

sup
(
C
∩
δ
)
=
δ
{\displaystyle \sup(C\cap \delta )=\delta }
. The set

C
{\displaystyle C}
 is *closed* in

κ
{\displaystyle \kappa }
 if it contains all of its limit points below

κ
{\displaystyle \kappa }
. A set that is both closed and unbounded is commonly referred to as a *[club set](/wiki/Club_set)*.

Examples of club sets are fundamental to set theory. The set of all [limit ordinals](/wiki/Limit_ordinal) less than

κ
{\displaystyle \kappa }
 is a club set, as there is always a limit ordinal greater than any given ordinal below

κ
{\displaystyle \kappa }
, and a limit of limit ordinals is itself a limit ordinal. If

κ
{\displaystyle \kappa }
 is a limit cardinal, the set of all [cardinals](/wiki/Cardinal_number) below

κ
{\displaystyle \kappa }
 is unbounded, and its set of limit points—the [limit cardinals](/wiki/Limit_cardinal)—forms a closed unbounded set. Furthermore, if

κ
{\displaystyle \kappa }
 is a [strong limit cardinal](/wiki/Strong_limit_cardinal) (such as an [inaccessible cardinal](/wiki/Inaccessible_cardinal)), the set of strong limit cardinals below

κ
{\displaystyle \kappa }
 is also a club set. Another significant example arises from [normal functions](/wiki/Normal_function) (functions

f
:
κ
→
κ
{\displaystyle f:\kappa \to \kappa }
 that are strictly increasing and continuous); the range of any normal function is a closed unbounded subset of

κ
{\displaystyle \kappa }
.

Club sets possess structural properties that allow them to generate a [filter](/wiki/Filter_(mathematics)). Because

κ
{\displaystyle \kappa }
 is regular and uncountable, the intersection of any two club sets is also a club set. More generally, the intersection of fewer than

κ
{\displaystyle \kappa }
 club sets is a club set. Consequently, the collection of all subsets of

κ
{\displaystyle \kappa }
 that contain a club set forms a

κ
{\displaystyle \kappa }
-complete non-principal filter, known as the *closed unbounded filter* (or [club filter](/wiki/Club_filter)).

A subset

S
⊆
κ
{\displaystyle S\subseteq \kappa }
 is termed *stationary* if it has a non-empty intersection with every closed unbounded set in

κ
{\displaystyle \kappa }
. Intuitively, stationary sets are "large" enough that they cannot be avoided by any club set. Using the notation of filters, a set is stationary if and only if it does not belong to the dual ideal of the club filter (the ideal of non-stationary sets). While every club set is stationary, not every stationary set is a club; for instance, a stationary set

S
{\displaystyle S}
 may fail to be closed. Furthermore, while the intersection of a stationary set and a club set is stationary, the intersection of two stationary sets may be empty.

The distinction between club sets and stationary sets is central to the definitions of certain [large cardinals](/wiki/Large_cardinal). If

κ
{\displaystyle \kappa }
 is the smallest [inaccessible cardinal](/wiki/Inaccessible_cardinal), the set of singular strong limit cardinals below

κ
{\displaystyle \kappa }
 forms a closed unbounded set. Because this club set contains no regular cardinals, the set of regular cardinals below the first inaccessible is not stationary. This remains true if

κ
{\displaystyle \kappa }
 is the

n
{\displaystyle n}
-th inaccessible cardinal for some

n
<
κ
{\displaystyle n<\kappa }
; the regular cardinals below it will not form a stationary set. A cardinal

κ
{\displaystyle \kappa }
 is defined as a [Mahlo cardinal](/wiki/Mahlo_cardinal) precisely when the set of regular cardinals below it is stationary. By relaxing the condition on the limit cardinals, one defines a cardinal as *weakly Mahlo* if it is [weakly inaccessible](/wiki/Weakly_inaccessible) and the set of regular cardinals below it is stationary.

The closed unbounded filter is not an [ultrafilter](/wiki/Ultrafilter) under the standard Zermelo–Fraenkel set theory with the Axiom of Choice (ZFC). This is because one can find two disjoint stationary sets, which precludes the filter from deciding membership for every subset. For any regular cardinal

κ
>

ω

1
{\displaystyle \kappa >\omega \_{1}}
, the set of ordinals with [cofinality](/wiki/Cofinality)

ω
{\displaystyle \omega }
 and the set of ordinals with cofinality

ω

1
{\displaystyle \omega \_{1}}
 are disjoint stationary subsets of

κ
{\displaystyle \kappa }
. In the specific case of

κ
=

ω

1
{\displaystyle \kappa =\omega \_{1}}
, the non-existence of an ultrafilter relies on the [Axiom of Choice](/wiki/Axiom_of_Choice). Under ZFC, the set of limit ordinals in

ω

1
{\displaystyle \omega \_{1}}
 can be partitioned into

ω

1
{\displaystyle \omega \_{1}}
 disjoint stationary sets (a result related to [Fodor's lemma](/wiki/Fodor%27s_lemma)). However, in models of set theory without the Axiom of Choice, such as those satisfying the [Axiom of determinacy](/wiki/Axiom_of_determinacy), the club filter on

ω

1
{\displaystyle \omega \_{1}}
 can be an ultrafilter, a property connected to

ω

1
{\displaystyle \omega \_{1}}
 being a [measurable cardinal](/wiki/Measurable_cardinal) in those contexts.

These definitions generalize to proper classes of ordinals. A class

C
{\displaystyle C}
 of ordinals is unbounded if it contains arbitrarily large ordinals, and closed if the limit of any sequence of ordinals in

C
{\displaystyle C}
 is also in

C
{\displaystyle C}
. This topological definition is equivalent to assuming the indexing class-function of

C
{\displaystyle C}
 is continuous. Notable examples of closed unbounded classes include the class of all infinite cardinals, the class of [limit cardinals](/wiki/Limit_cardinal), and the class of [fixed points](/wiki/Fixed_point_(mathematics)) of the

ℵ
{\displaystyle \aleph }
-function. In contrast, the class of [regular cardinals](/wiki/Regular_cardinal) is unbounded but not closed. A class is stationary if it intersects every closed unbounded class.

## Some "large" countable ordinals

Further information: [Large countable ordinal](/wiki/Large_countable_ordinal)

As mentioned above (see [Cantor normal form](/wiki/Ordinal_arithmetic#Cantor_normal_form)), the ordinal ε0 is the smallest satisfying the equation ⁠

ω

α
=
α
{\displaystyle \omega ^{\alpha }=\alpha }
⁠, so it is the limit of the sequence 0, 1, ⁠

ω
{\displaystyle \omega }
⁠, ⁠

ω

ω
{\displaystyle \omega ^{\omega }}
⁠, ⁠

ω

ω

ω
{\displaystyle \omega ^{\omega ^{\omega }}}
⁠, etc. Many ordinals can be defined in such a manner as fixed points of certain ordinal functions (the

ι
{\displaystyle \iota }
-th ordinal such that

ω

α
=
α
{\displaystyle \omega ^{\alpha }=\alpha }
 is called ⁠

ε

ι
{\displaystyle \varepsilon \_{\iota }}
⁠, then one could go on trying to find the

ι
{\displaystyle \iota }
-th ordinal such that ⁠

ε

α
=
α
{\displaystyle \varepsilon \_{\alpha }=\alpha }
⁠, "and so on", but all the subtlety lies in the "and so on"). One could try to do this systematically, but no matter what system is used to define and construct ordinals, there is always an ordinal that lies just above all the ordinals constructed by the system. Perhaps the most important ordinal that limits a system of construction in this manner is the [Church–Kleene ordinal](/wiki/Church%E2%80%93Kleene_ordinal),

ω

1

C
K
{\displaystyle \omega \_{1}^{\mathrm {CK} }}
 (despite the

ω

1
{\displaystyle \omega \_{1}}
 in the name, this ordinal is countable), which is the smallest ordinal that is not a [computable ordinal](/wiki/Computable_ordinal) (i.e., the order type of a well-ordering ⁠

<
{\displaystyle <}
⁠ of the natural numbers such that the predicate ⁠

x
<
y
{\displaystyle x<y}
⁠ is [computable](/wiki/Computable_function)). Considerably large ordinals can be defined below ⁠

ω

1

C
K
{\displaystyle \omega \_{1}^{\mathrm {CK} }}
⁠, however, which measure the [proof-theoretic strength](/wiki/Ordinal_analysis) of certain [formal systems](/wiki/Formal_system) (for example,

ε

0
{\displaystyle \varepsilon \_{0}}
 measures the strength of [Peano arithmetic](/wiki/Peano_axioms)). Large countable ordinals such as countable [admissible ordinals](/wiki/Admissible_ordinal) can also be defined above the Church-Kleene ordinal, which are of interest in various parts of logic.

## Topology and ordinals

Further information: [Order topology](/wiki/Order_topology)

Any ordinal number can be made into a [topological space](/wiki/Topological_space) by endowing it with the [order topology](/wiki/Order_topology). This topology is [discrete](/wiki/Discrete_topology) if and only if it is less than or equal to ω. In contrast, a subset of ω + 1 is open in the order topology if and only if either it is [cofinite](/wiki/Cofinite) or it does not contain ω as an element.

See the [Topology and ordinals](/wiki/Order_topology#Topology_and_ordinals) section of the "Order topology" article.

## History

The transfinite ordinal numbers, which first appeared in 1883, originated in Cantor's work with [derived sets](/wiki/Derived_set_(mathematics)). If *P* is a set of real numbers, the derived set *P′* is the set of [limit points](/wiki/Limit_point) of *P*. In 1872, Cantor generated the sets *P*(*n*) by applying the derived set operation *n* times to *P*. In 1880, he pointed out that these sets form the sequence *P'* ⊇ ··· ⊇ *P*(*n*) ⊇ *P*(*n* + 1) ⊇ ···, and he continued the derivation process by defining *P*(∞) as the intersection of these sets. Then he iterated the derived set operation and intersections to extend his sequence of sets into the infinite: *P*(∞) ⊇ *P*(∞ + 1) ⊇ *P*(∞ + 2) ⊇ ··· ⊇ *P*(2∞) ⊇ ··· ⊇ *P*(∞2) ⊇ ···. The superscripts containing ∞ are just indices defined by the derivation process.

Cantor used these sets in the theorems:

1. If *P*(*α*) = ∅ for some index *α*, then *P′* is countable;
2. Conversely, if *P′* is countable, then there is an index *α* such that *P*(*α*) = ∅.

These theorems are proved by partitioning *P′* into [pairwise disjoint](/wiki/Pairwise_disjoint) sets: *P′* = (*P′*\ *P*(2)) ∪ (*P*(2) \ *P*(3)) ∪ ··· ∪ (*P*(∞) \ *P*(∞ + 1)) ∪ ··· ∪ *P*(*α*). For *β* < *α*: since *P*(*β* + 1) contains the limit points of *P*(*β*), the sets *P*(*β*) \ *P*(*β* + 1) have no limit points. Hence, they are [discrete sets](/wiki/Discrete_set), so they are countable. Proof of first theorem: If *P*(*α*) = ∅ for some index *α*, then *P′* is the countable union of countable sets. Therefore, *P′* is countable.

The second theorem requires proving the existence of an *α* such that *P*(*α*) = ∅. To prove this, Cantor considered the set of all *α* having countably many predecessors. To define this set, he defined the transfinite ordinal numbers and transformed the infinite indices into ordinals by replacing ∞ with *ω*, the first transfinite ordinal number. Cantor called the set of finite ordinals the first **number class**. The second number class is the set of ordinals whose predecessors form a countably infinite set. The set of all *α* having countably many predecessors—that is, the set of countable ordinals—is the union of these two number classes. Cantor proved that the cardinality of the second number class is the first uncountable cardinality.

Cantor's second theorem becomes: If *P′* is countable, then there is a countable ordinal *α* such that *P*(*α*) = ∅. Its proof uses [proof by contradiction](/wiki/Proof_by_contradiction). Let *P′* be countable, and assume there is no such α. This assumption produces two cases.

- Case 1: *P*(*β*) \ *P*(*β* + 1) is non-empty for all countable *β*. Since there are uncountably many of these pairwise disjoint sets, their union is uncountable. This union is a subset of *P′*, so *P'*  is uncountable.
- Case 2: *P*(*β*) \ *P*(*β* + 1) is empty for some countable *β*. Since *P*(*β* + 1) ⊆ *P*(*β*), this implies *P*(*β* + 1) = *P*(*β*). Thus, *P*(*β*) is a [perfect set](/wiki/Derived_set_(mathematics)#Properties), so it is uncountable. Since *P*(*β*) ⊆ *P′*, the set *P′* is uncountable.

In both cases, *P′* is uncountable, which contradicts *P′* being countable. Therefore, there is a countable ordinal *α* such that *P*(*α*) = ∅. Cantor's work with derived sets and ordinal numbers led to the [Cantor-Bendixson theorem](/wiki/Cantor-Bendixson_theorem).

Using successors, limits, and cardinality, Cantor generated an unbounded sequence of ordinal numbers and number classes. The (*α* + 1)-th number class is the set of ordinals whose predecessors form a set of the same cardinality as the *α*-th number class. The cardinality of the (*α* + 1)-th number class is the cardinality immediately following that of the *α*-th number class. For a limit ordinal *α*, the *α*-th number class is the union of the *β*-th number classes for *β* < *α*. Its cardinality is the limit of the cardinalities of these number classes.

If *n* is finite, the *n*-th number class has cardinality ⁠

ℵ

n
−
1
{\displaystyle \aleph \_{n-1}}
⁠. If *α* ≥ *ω*, the *α*-th number class has cardinality ⁠

ℵ

α
{\displaystyle \aleph \_{\alpha }}
⁠. Therefore, the cardinalities of the number classes correspond one-to-one with the [aleph numbers](/wiki/Aleph_number). Also, the *α*-th number class consists of ordinals different from those in the preceding number classes if and only if *α* is a non-limit ordinal. Therefore, the non-limit number classes partition the ordinals into pairwise disjoint sets.

## See also

- [Counting](/wiki/Counting)
- [Even and odd ordinals](/wiki/Even_and_odd_ordinals)
- [First uncountable ordinal](/wiki/First_uncountable_ordinal)
- [Ordinal space](/wiki/Order_topology#Ordinal_space)
- [Surreal number](/wiki/Surreal_number), a generalization of ordinals which includes negative, real, and infinitesimal values.

## Notes

## Citations

## References

## External links

- ["Ordinal number"](https://www.encyclopediaofmath.org/index.php?title=Ordinal_number), *[Encyclopedia of Mathematics](/wiki/Encyclopedia_of_Mathematics)*, [EMS Press](/wiki/European_Mathematical_Society), 2001 [1994]
- [Ordinals at ProvenMath](http://www.apronus.com/provenmath/ordinals.htm)
- [Ordinal calculator](https://web.archive.org/web/20220121063447/http://www.mtnmath.com/ord/index.html) [GPL'd](/wiki/GNU_General_Public_License) free software for computing with ordinals and ordinal notations
- Chapter 4 of [Don Monk's](http://math.colorado.edu/~monkd) [lecture notes](https://web.archive.org/web/20150429210249/http://euclid.colorado.edu/~monkd/m8714.html) on set theory is an introduction to ordinals.
