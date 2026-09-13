# Three-body problem

This article is about the physics problem. For the novel by Liu Cixin, see [The Three-Body Problem (novel)](/wiki/The_Three-Body_Problem_(novel)).

Approximate trajectories of three identical bodies located at the vertices of a scalene triangle and having zero initial velocities. The [center of mass](/wiki/Center_of_mass), in accordance with the [law of conservation of momentum](/wiki/Law_of_conservation_of_momentum), remains in place.

In [physics](/wiki/Physics), specifically [classical mechanics](/wiki/Classical_mechanics), the **three-body problem** is to take the initial positions and [velocities](/wiki/Velocity) (or [momenta](/wiki/Momentum)) of three [point masses](/wiki/Point_mass) orbiting each other in space and then to calculate their subsequent trajectories using [Newton's laws of motion](/wiki/Newton%27s_laws_of_motion) and [Newton's law of universal gravitation](/wiki/Newton%27s_law_of_universal_gravitation).

Unlike the [two-body problem](/wiki/Two-body_problem), the three-body problem has no general [closed-form analytic solution](/wiki/Closed-form_expression). The [differential equations](/wiki/Differential_equation) that govern the movements of three gravitating bodies are not [integrable](/wiki/Integrable_system) and cannot be solved to give explicit formulas for the positions of the bodies as a function of [time](/wiki/Time). For most [initial conditions](/wiki/Initial_condition), the [dynamical system](/wiki/Dynamical_system) for three orbiting bodies is [chaotic](/wiki/Chaos_theory), and the only way to predict their motions is to estimate them using [numerical methods](/wiki/Numerical_method).

The three-body problem is a special case of the [n-body problem](/wiki/N-body_problem). Historically, the first specific three-body problem to receive extended study was the one involving the [Earth](/wiki/Earth), the [Moon](/wiki/Moon), and the [Sun](/wiki/Sun). In an extended modern sense, a three-body problem is any problem in classical mechanics or [quantum mechanics](/wiki/Quantum_mechanics) that models the motion of three particles.

## Mathematical description

The mathematical statement of the three-body problem can be given in terms of the Newtonian equations of motion for vector positions

 

r

i
=
(

x

i
,

y

i
,

z

i
)
 
{\displaystyle \ \mathbf {r} \_{i}=(x\_{i},y\_{i},z\_{i})\ }
 of three gravitationally interacting bodies with masses

m

i
{\displaystyle m\_{i}}
:

r
¨

1

=
−
G

m

2

(

r

1
−

r

2
)

 

|

r

1
−

r

2
|

3
−
G

m

3

(

r

1
−

r

3
)

 

|

r

1
−

r

3
|

3
 
,

r
¨

2

=
−
G

m

3

(

r

2
−

r

3
)

 

|

r

2
−

r

3
|

3
−
G

m

1

(

r

2
−

r

1
)

 

|

r

2
−

r

1
|

3
 
,

r
¨

3

=
−
G

m

1

(

r

3
−

r

1
)

 

|

r

3
−

r

1
|

3
−
G

m

2

(

r

3
−

r

2
)

 

|

r

3
−

r

2
|

3
 
.
{\displaystyle {\begin{aligned}{\ddot {\mathbf {r} }}\_{1}&=-Gm\_{2}{\frac {\left(\mathbf {r} \_{1}-\mathbf {r} \_{2}\right)}{\ \left|\mathbf {r} \_{1}-\mathbf {r} \_{2}\right|^{3}}}-Gm\_{3}{\frac {\left(\mathbf {r} \_{1}-\mathbf {r} \_{3}\right)}{\ \left|\mathbf {r} \_{1}-\mathbf {r} \_{3}\right|^{3}}}\ ,\\{\ddot {\mathbf {r} }}\_{2}&=-Gm\_{3}{\frac {\left(\mathbf {r} \_{2}-\mathbf {r} \_{3}\right)}{\ \left|\mathbf {r} \_{2}-\mathbf {r} \_{3}\right|^{3}}}-Gm\_{1}{\frac {\left(\mathbf {r} \_{2}-\mathbf {r} \_{1}\right)}{\ \left|\mathbf {r} \_{2}-\mathbf {r} \_{1}\right|^{3}}}\ ,\\{\ddot {\mathbf {r} }}\_{3}&=-Gm\_{1}{\frac {\left(\mathbf {r} \_{3}-\mathbf {r} \_{1}\right)}{\ \left|\mathbf {r} \_{3}-\mathbf {r} \_{1}\right|^{3}}}-Gm\_{2}{\frac {\left(\mathbf {r} \_{3}-\mathbf {r} \_{2}\right)}{\ \left|\mathbf {r} \_{3}-\mathbf {r} \_{2}\right|^{3}}}~.\end{aligned}}}
 where

 
G
 
{\displaystyle \ G\ }
 is the [gravitational constant](/wiki/Gravitational_constant).

As astronomer Juhan Frank describes, "These three second-order vector [differential equations](/wiki/Differential_equation) are equivalent to 18 first order scalar differential equations." As June Barrow-Green notes with regard to an alternative presentation, if

P

i
{\displaystyle P\_{i}}
 represent three particles with masses

m

i
{\displaystyle m\_{i}}
, distances

 

P

i

P

j
=

r

i
j
 
,
{\displaystyle \ P\_{i}P\_{j}=r\_{ij}\ ,}
 and coordinates

 

q

i
j
 
{\displaystyle \ q\_{ij}\ }


 
(
i
,
j
=
1
,
2
,
3
)
 
{\displaystyle \ (i,j=1,2,3)\ }
in an inertial coordinate system ... the problem is described by nine second-order differential equations.

The problem can also be stated equivalently in the [Hamiltonian formalism](/wiki/Hamiltonian_formalism), in which case it is described by a set of 18 first-order differential equations, one for each component of the positions

 

r

i
 
{\displaystyle \ \mathbf {r} \_{i}\ }
 and momenta

 

p

i
 
{\displaystyle \ \mathbf {p} \_{i}\ }
:

d
 

r

i

d
 
t
=

∂
 

H

∂
 

p

i
 
,

d
 

p

i

d
 
t
=
−

∂
 

H

∂
 

r

i
 
,
{\displaystyle {\frac {\mathrm {d} \ \mathbf {r} \_{i}}{\mathrm {d} \ t}}={\frac {\partial \ {\mathcal {H}}}{\partial \ \mathbf {p} \_{i}}}\ ,\qquad {\frac {\mathrm {d} \ \mathbf {p} \_{i}}{\mathrm {d} \ t}}=-{\frac {\partial \ {\mathcal {H}}}{\partial \ \mathbf {r} \_{i}}}\ ,}
where

H
{\displaystyle {\mathcal {H}}}
 is the [Hamiltonian](/wiki/Hamiltonian_mechanics#Mathematical_formalism):

H
 
=
 
−

G

m

1

m

2

|

r

1
−

r

2
|
 
−
 

G

m

2

m

3

|

r

3
−

r

2
|
 
−
 

G

m

3

m

1

|

r

3
−

r

1
|
 
+
 

|

p

1
|

2

2

m

1
 
+
 

|

p

2
|

2

2

m

2
 
+
 

|

p

3
|

2

2

m

3
 
.
{\displaystyle {\mathcal {H}}\ =\ -{\frac {Gm\_{1}m\_{2}}{\left|\mathbf {r} \_{1}-\mathbf {r} \_{2}\right|}}\ -\ {\frac {Gm\_{2}m\_{3}}{\left|\mathbf {r} \_{3}-\mathbf {r} \_{2}\right|}}\ -\ {\frac {Gm\_{3}m\_{1}}{\left|\mathbf {r} \_{3}-\mathbf {r} \_{1}\right|}}\ +\ {\frac {\left|\mathbf {p} \_{1}\right|^{2}}{2m\_{1}}}\ +\ {\frac {\left|\mathbf {p} \_{2}\right|^{2}}{2m\_{2}}}\ +\ {\frac {\left|\mathbf {p} \_{3}\right|^{2}}{2m\_{3}}}~.}

In this case,

H
{\displaystyle {\mathcal {H}}}
 is simply the total energy of the system, gravitational plus kinetic.

### Restricted three-body problem

The circular restricted three-body problem

In the *restricted three-body problem* formulation, in the description of Barrow-Green,

> two... bodies revolve around their centre of mass in circular orbits under the influence of their mutual gravitational attraction, and... form a two-body system... [whose] motion is known. A third body (generally known as a planetoid), assumed massless with respect to the other two, moves in the plane defined by the two revolving bodies and, while being gravitationally influenced by them, exerts no influence of its own.

Per Barrow-Green, "[t]he problem is then to ascertain the motion of the third body."

The restricted three-body problem is easier to analyze theoretically than the full problem. It is of practical interest as well since it accurately describes many real-world problems, the most important example being the Earth–Moon–Sun system. For these reasons, it has occupied an important role in the historical development of the three-body problem.

The restricted 3-body problem has a 4-dimensional [phase space](/wiki/Phase_space), but only one [conserved quantity](/wiki/Conserved_quantity), the [Jacobi integral](/wiki/Jacobi_integral). It was shown by [Heinrich Bruns](/wiki/Heinrich_Bruns) that there are no more [algebraic](/wiki/Algebraic_function) conserved quantities, and by [Henri Poincaré](/wiki/Henri_Poincar%C3%A9) in 1889 that there are no more [analytic](/wiki/Analytic_function) conserved quantities. Therefore, since the dimension of the phase space is larger than the number of [constants of motion](/wiki/Constants_of_motion), the system is *not* [exactly solvable](/wiki/Exactly_solvable); in fact, it is chaotic.

Depending on the value of the [Jacobi integral](/wiki/Jacobi_integral), a body initially orbiting the larger mass may be able to be captured by the secondary mass or be ejected via Lagrange points L2 or L3.

A variant of this problem, where the two large bodies both exert [radiation pressure](/wiki/Radiation_pressure), results in the addition of four additional [equilibrium points](/wiki/Equilibrium_points) in addition to the five classical [Lagrange points](/wiki/Lagrange_points).

## Solutions

### General solution

While a system of 3 bodies interacting gravitationally is [chaotic](/wiki/Chaos_theory), a system of 3 bodies interacting [elastically](/wiki/Elastic_force) is not.

There is no general [closed-form solution](/wiki/Closed-form_expression) to the three-body problem. In other words, it does not have a general solution that can be expressed in terms of a finite number of standard mathematical operations. Moreover, the motion of three bodies is generally non-repeating, except in special cases.

However, in 1912 the [Finnish](/wiki/Finland) [mathematician](/wiki/Mathematics) [Karl Fritiof Sundman](/wiki/Karl_Fritiof_Sundman) proved that there exists an [analytic solution](/wiki/Analytic_solution) to the three-body problem in the form of a [Puiseux series](/wiki/Puiseux_series), specifically a [power series](/wiki/Power_series) in terms of powers of *t*1/3. This series converges for all real t, except for initial conditions corresponding to zero [angular momentum](/wiki/Angular_momentum). In practice, the latter restriction is insignificant since initial conditions with zero angular momentum are rare, having [Lebesgue measure](/wiki/Lebesgue_measure) zero.

An important issue in proving this result is the fact that the [radius of convergence](/wiki/Radius_of_convergence) for this series is determined by the distance to the nearest singularity. Therefore, it is necessary to study the possible singularities of the three-body problem. As is briefly discussed below, the only singularities in the three-body problem are binary collisions (collisions between two particles at an instant) and triple collisions (collisions between three particles at an instant).

Collisions of any number are somewhat improbable, since it has been shown that they correspond to a set of initial conditions of measure zero. But there is no criterion known to be put on the initial state to avoid collisions for the corresponding solution. So Sundman's strategy consisted of the following steps:

1. Using an appropriate change of variables to continue analyzing the solution beyond the binary collision, in a process known as [regularization](/wiki/Regularization_(physics)).
2. Proving that triple collisions only occur when the angular momentum **L** vanishes. By restricting the initial data to **L** ≠ **0**, he removed all *real* singularities from the transformed equations for the three-body problem.
3. Showing that if **L** ≠ **0**, then not only can there be no triple collision, but the system is strictly bounded away from a triple collision. This implies, by [Cauchy](/wiki/Cauchy)'s [existence theorem](/wiki/Existence_theorem) for differential equations, that there are no complex singularities in a strip (depending on the value of **L**) in the complex plane centered around the real axis (related to the [Cauchy–Kovalevskaya theorem](/wiki/Cauchy%E2%80%93Kovalevskaya_theorem)).
4. Find a conformal transformation that maps this strip into the unit disc. For example, if *s* = *t*1/3 (the new variable after the regularization) and if |ln *s*| ≤ *β*, then this map is given by

   σ
   =

   e

   π
   s

   2
   β
   −
   1

   e

   π
   s

   2
   β
   +
   1
   .
   {\displaystyle \sigma ={\frac {e^{\frac {\pi s}{2\beta }}-1}{e^{\frac {\pi s}{2\beta }}+1}}.}

This finishes the proof of Sundman's theorem.

The corresponding series converges extremely slowly. That is, obtaining a value of meaningful precision requires so many terms that this solution is of little practical use. Indeed, in 1930, David Beloriszky calculated that if Sundman's series were to be used for astronomical observations, then the computations would involve at least 108000000 terms.

### Special-case solutions

Twenty examples of special periodic solutions to the three-body problem

In 1767, [Leonhard Euler](/wiki/Leonhard_Euler) found three families of periodic solutions in which the three masses are [collinear](/wiki/Collinear) at each instant. In 1772, [Lagrange](/wiki/Joseph_Louis_Lagrange) found a family of solutions in which the three masses form an equilateral triangle at each instant. Together with Euler's collinear solutions, these solutions form the [central configurations](/wiki/Central_configuration) for the three-body problem. These solutions are valid for any mass ratios, and the masses move on [Keplerian ellipses](/wiki/Kepler_orbit). These four families are the only known solutions for which there are explicit analytic formulas. In the special case of the [circular restricted three-body problem](/wiki/Circular_restricted_three-body_problem), these solutions, viewed in a frame rotating with the primaries, become points called [Lagrangian points](/wiki/Lagrangian_point) and labeled L1, L2, L3, L4, and L5, with L4 and L5 being symmetric instances of Lagrange's solution.

In work summarized in 1892–1899, [Henri Poincaré](/wiki/Henri_Poincar%C3%A9) established the existence of an infinite number of periodic solutions to the restricted three-body problem, together with techniques for continuing these solutions into the general three-body problem.

In 1893, Meissel stated what is now called the Pythagorean three-body problem: three masses in the ratio 3:4:5 are placed at rest at the vertices of a [3:4:5 right triangle](/wiki/Special_right_triangle), with the heaviest body at the right angle and the lightest at the smaller acute angle. Burrau further investigated this problem in 1913. In 1967 [Victor Szebehely](/wiki/Victor_Szebehely) and C. Frederick Peters established eventual escape of the lightest body for this problem using numerical integration, while at the same time finding a nearby periodic solution.

In the 1970s, [Michel Hénon](/wiki/Michel_H%C3%A9non) and [Roger A. Broucke](/wiki/Roger_A._Broucke) each found a set of solutions that form part of the same family of solutions: the Broucke–Hénon–Hadjidemetriou family. In this family, the three objects all have the same mass and can exhibit both retrograde and direct forms. In some of Broucke's solutions, two of the bodies follow the same path.

In 1993, physicist [Cris Moore](/wiki/Cris_Moore) at the [Santa Fe Institute](/wiki/Santa_Fe_Institute) found a zero angular momentum solution with three equal masses moving around a figure-eight shape. In 2000, mathematicians [Alain Chenciner](/wiki/Alain_Chenciner) and Richard Montgomery proved its formal existence. The solution has been shown numerically to be stable for small perturbations of the mass and orbital parameters, which makes it possible for such orbits to be observed in the physical universe. But it has been argued that this is unlikely since the domain of stability is small. For instance, the probability of a binary–binary [scattering](/wiki/Scattering) event resulting in a figure-8 orbit has been estimated to be a small fraction of a percent.

In 2013, physicists Milovan Šuvakov and Veljko Dmitrašinović at the Institute of Physics in Belgrade discovered 13 new families of solutions for the equal-mass zero-angular-momentum three-body problem.

In 2015, physicist Ana Hudomal discovered 14 new families of solutions for the equal-mass zero-angular-momentum three-body problem.

In 2017, researchers Xiaoming Li and [Shijun Liao](/wiki/Shijun_Liao) found 669 new periodic orbits of the equal-mass zero-angular-momentum three-body problem. This was followed in 2018 by an additional 1,223 new solutions for a zero-angular-momentum system of unequal masses.

In 2018, Li and Liao reported 234 solutions to the unequal-mass "free-fall" three-body problem. The free-fall formulation starts with all three bodies at rest. Because of this, the masses in a free-fall configuration do not orbit in a closed "loop", but travel forward and backward along an open "track".

In 2023, Ivan Hristov, Radoslava Hristova, Dmitrašinović, and Kiyotaka Tanikawa published a search for "periodic free-fall orbits" in the three-body problem, limited to the equal-mass case, and found 12,409 distinct solutions.

### Numerical approaches

Using a computer, the problem may be solved to arbitrarily high precision using [numerical integration](/wiki/Numerical_integration). There have been attempts at creating computer programs that [numerically solve](/wiki/Numerical_analysis) the three-body problem (and by extension, the [n-body problem](/wiki/N-body_problem)) involving both electromagnetic and gravitational interactions, and incorporating modern theories of physics such as [special relativity](/wiki/Special_relativity). In addition, using the theory of [random walks](/wiki/Random_walks), an approximate [probability](/wiki/Probability) of different outcomes may be computed.

## History

The gravitational problem of three bodies in its traditional sense dates in substance from 1687, when [Isaac Newton](/wiki/Isaac_Newton) published his *[Philosophiæ Naturalis Principia Mathematica](/wiki/Philosophi%C3%A6_Naturalis_Principia_Mathematica).* Newton, having solved the [two-body problem](/wiki/Two-body_problem), tried to discover whether any long-term stability is possible for a system such as the [Earth](/wiki/Earth), the [Moon](/wiki/Moon), and [the Sun](/wiki/Sun). Guided by major [Renaissance](/wiki/Renaissance) astronomers [Nicolaus Copernicus](/wiki/Nicolaus_Copernicus), [Tycho Brahe](/wiki/Tycho_Brahe) and [Johannes Kepler](/wiki/Johannes_Kepler), Newton introduced later generations to the beginning of the gravitational three-body problem. In Proposition 66 of Book 1 of the *Principia*, and its 22 Corollaries, Newton took the first steps in the definition and study of the problem of the movements of three massive bodies subject to their mutually perturbing gravitational attractions. In Propositions 25 to 35 of Book 3, Newton also took the first steps in applying his results of Proposition 66 to the [lunar theory](/wiki/Lunar_theory#Newton), the motion of the Moon under the gravitational influence of Earth and the Sun. Later, this problem was also applied to other planets' interactions with the Earth and the Sun.

The physical problem was first addressed by [Amerigo Vespucci](/wiki/Amerigo_Vespucci) and subsequently by [Galileo Galilei](/wiki/Galileo_Galilei), as well as [Simon Stevin](/wiki/Simon_Stevin), but they did not realize what they contributed. Though Galileo determined that the speed of fall of all bodies changes uniformly and in the same way, he did not apply it to planetary motions. Whereas in 1499, Vespucci used knowledge of the position of the Moon to determine his position in Brazil. It became of technical importance in the 1720s, as an accurate solution would apply to navigation, specifically for the [determination of longitude at sea](/wiki/History_of_longitude#Problem_of_longitude), solved in practice by [John Harrison](/wiki/John_Harrison)'s invention of the [marine chronometer](/wiki/Marine_chronometer). However, the accuracy of the [lunar theory](/wiki/Lunar_theory) was low, due to the perturbing effect of the Sun and planets on the motion of the Moon around Earth.

[Jean le Rond d'Alembert](/wiki/Jean_le_Rond_d%27Alembert) and [Alexis Clairaut](/wiki/Alexis_Clairaut), who developed a longstanding rivalry, both attempted to analyze the problem in some degree of generality; they submitted their competing first analyses to the Académie Royale des Sciences in 1747. It was in connection with their research, in Paris during the 1740s, that the name "three-body problem" ([French](/wiki/French_language): *Problème des trois Corps*) began to be commonly used. An account published in 1761 by Jean le Rond d'Alembert indicates that the name was first used in 1747.

From the end of the 19th century to early 20th century, the approach to solve the three-body problem with the usage of short-range attractive two-body forces was developed by scientists, which offered P. F. Bedaque, H.-W. Hammer and U. van Kolck an idea to renormalize the short-range three-body problem, providing scientists a rare example of a [renormalization group](/wiki/Renormalization_group) [limit cycle](/wiki/Limit_cycle) at the beginning of the 21st century. [George William Hill](/wiki/George_William_Hill) worked on the restricted problem in the late 19th century with an application of motion of [Venus](/wiki/Venus) and [Mercury](/wiki/Mercury_(planet)).

At the beginning of the 20th century, [Karl Sundman](/wiki/Karl_F._Sundman) approached the problem mathematically and systematically by providing a functional theoretical proof to the problem valid for all values of time. It was the first time scientists theoretically solved the three-body problem. However, because there was not a qualitative enough solution of this system, and it was too slow for scientists to practically apply it, this solution still left some issues unresolved. In the 1970s, implication to three-body from two-body forces had been discovered by [V. Efimov](/wiki/Vitaly_Efimov), which was named the [Efimov effect](/wiki/Efimov_effect).

In 2017, [Shijun Liao](/wiki/Liao_Shijun) and Xiaoming Li applied a new strategy of numerical simulation for chaotic systems called the clean numerical simulation (CNS), with the use of a national supercomputer, to successfully gain 695 families of periodic solutions of the three-body system with equal mass.

In 2019, Breen et al. announced a fast [neural network](/wiki/Neural_network) solver for the three-body problem, trained using a numerical integrator.

In September 2023, several possible solutions have been found to the problem, according to reports.

## Other problems involving three bodies

The term "three-body problem" is sometimes used in the more general sense to refer to any physical problem involving the interaction of three bodies.

A quantum-mechanical analogue of the gravitational three-body problem in classical mechanics is the [helium atom](/wiki/Helium_atom),
in which a [helium](/wiki/Helium) nucleus and two [electrons](/wiki/Electrons) interact according to the [inverse-square](/wiki/Inverse-square) [Coulomb interaction](/wiki/Coulomb_interaction). Like the
gravitational three-body problem, the helium atom cannot be solved exactly.

In both classical and quantum mechanics, however, there exist nontrivial interaction laws besides the inverse-square force that do lead to exact analytic three-body solutions. One such model consists of a combination of [harmonic attraction](/wiki/Harmonic_oscillator) and a repulsive inverse-cube force. This model is considered nontrivial since it is associated with a set of nonlinear differential equations containing singularities (compared with, e.g., harmonic interactions alone, which lead to an easily solved system of linear differential equations). In these two respects, it is analogous to (insoluble) models having Coulomb interactions, and as a result, it has been suggested as a tool for intuitively understanding physical systems like the helium atom.

Within the [point vortex model](/wiki/Two-dimensional_point_vortex_gas), the motion of [vortices](/wiki/Vortex) in a two-dimensional ideal fluid is described by equations of motion that contain only first-order time derivatives. i.e., in contrast to Newtonian mechanics, it is the *velocity* and not the acceleration that is determined by their relative positions. As a consequence, the three-vortex problem is still [integrable](/wiki/Integrable_system), while at least four vortices are required to obtain chaotic behavior. One can draw parallels between the motion of a passive tracer particle in the velocity field of three vortices and the restricted three-body problem of Newtonian mechanics.

The gravitational three-body problem has also been studied using [general relativity](/wiki/General_relativity). Physically, a relativistic treatment becomes necessary in systems with very strong gravitational fields, such as near the [event horizon](/wiki/Event_horizon) of a [black hole](/wiki/Black_hole). However, the relativistic problem is considerably more difficult than in Newtonian mechanics, and [sophisticated numerical techniques](/wiki/Numerical_relativity) are required.
Even the full [two-body problem](/wiki/Two-body_problem_in_general_relativity) (i.e., for an arbitrary ratio of masses) does not have a rigorous analytic solution in general relativity.

## n-body problem

The three-body problem is a special case of the [n-body problem](/wiki/N-body_problem), which describes how n objects move under one of the physical forces, such as [gravity](/wiki/Gravity). These problems have a global analytical solution in the form of a convergent power series, as was proven by [Karl F. Sundman](/wiki/Karl_F._Sundman) for *n* = 3 and by [Qiudong Wang](/wiki/Qiudong_Wang) for *n* > 3 (see [n-body problem](/wiki/N-body_problem) for details). However, the Sundman and Wang series converge so slowly that they are useless for practical purposes; therefore, it is currently necessary to approximate solutions by [numerical analysis](/wiki/Numerical_analysis) in the form of [numerical integration](/wiki/Numerical_integration) or, for some cases, classical [trigonometric series](/wiki/Trigonometric_series) approximations (see [n-body simulation](/wiki/N-body_simulation)). Atomic systems, e.g., atoms, ions, and molecules, can be treated in terms of the quantum n-body problem. Among classical physical systems, the n-body problem usually refers to a [galaxy](/wiki/Galaxy) or to a [cluster of galaxies](/wiki/Cluster_of_galaxies); [planetary systems](/wiki/Planetary_systems), such as [stars](/wiki/Stars), [planets](/wiki/Planets), and their [satellites](/wiki/Satellites), can also be treated as n-body systems. Some applications are conveniently treated by [perturbation](/wiki/Perturbation_(astronomy)) theory, in which the system is considered as a two-body problem plus additional forces causing deviations from a hypothetical unperturbed two-body trajectory.

## See also

- [Few-body systems](/wiki/Few-body_systems)
- [Galaxy formation and evolution](/wiki/Galaxy_formation_and_evolution)
- [Gravity assist](/wiki/Gravity_assist)
- [Lagrange point](/wiki/Lagrange_point)
- [Low-energy transfer](/wiki/Low-energy_transfer)
- [Michael Minovitch](/wiki/Michael_Minovitch)
- [n-body simulation](/wiki/N-body_simulation)
- [Symplectic integrator](/wiki/Symplectic_integrator)
- [Sitnikov problem](/wiki/Sitnikov_problem)
- [Two-body problem](/wiki/Two-body_problem)
- [Synodic reference frame](/wiki/Synodic_reference_frame)
- [Triple star system](/wiki/Triple_star_system)
- [*The Three-Body Problem* (novel)](/wiki/The_Three-Body_Problem_(novel))
- [*Three-Body* (TV series)](/wiki/Three-Body)
- [*3 Body Problem* (TV series)](/wiki/3_Body_Problem_(TV_series))

## References

## Further reading

## External links

- [Chenciner, Alain](/wiki/Alain_Chenciner) (2007). ["Three body problem"](https://doi.org/10.4249%2Fscholarpedia.2111). *[Scholarpedia](/wiki/Scholarpedia)*. **2** (10): 2111. [Bibcode](/wiki/Bibcode_(identifier)):[2007SchpJ...2.2111C](https://ui.adsabs.harvard.edu/abs/2007SchpJ...2.2111C). [doi](/wiki/Doi_(identifier)):[10.4249/scholarpedia.2111](https://doi.org/10.4249%2Fscholarpedia.2111).
- [The '3-body problem' may not be so chaotic after all, new study suggests](https://www.livescience.com/physics-mathematics/the-3-body-problem-may-not-be-so-chaotic-after-all-new-study-suggests) (*Live Science,* October 22, 2024)
- [Physicists Discover a Whopping 13 New Solutions to Three-Body Problem](https://www.science.org/content/article/physicists-discover-whopping-13-new-solutions-three-body-problem) (*Science,* March 8, 2013)
