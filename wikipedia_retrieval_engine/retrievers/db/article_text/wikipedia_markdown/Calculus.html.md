# Calculus

This article is about the branch of mathematics. For other uses, see [Calculus (disambiguation)](/wiki/Calculus_(disambiguation)).

**Calculus** is the mathematical study of continuous change, and the principal precursor of modern [mathematical analysis](/wiki/Mathematical_analysis). Originally called **infinitesimal calculus** or the **calculus of infinitesimals**, it has two major branches, [differential calculus](/wiki/Differential_calculus) and [integral calculus](/wiki/Integral_calculus). Differential calculus studies [instantaneous rates of change](/wiki/Derivative) and [slopes](/wiki/Slope) of [curves](/wiki/Curve); [integral calculus](/wiki/Integral) studies accumulation of quantities and [areas](/wiki/Area) under or between curves. These two branches are related to each other by the [fundamental theorem of calculus](/wiki/Fundamental_theorem_of_calculus). Calculus uses [convergence](/wiki/Convergent_series) of [infinite sequences](/wiki/Infinite_sequences) and [infinite series](/wiki/Infinite_series) to a well-defined [mathematical limit](/wiki/Mathematical_limit).

Calculus is the "mathematical backbone" for solving problems in which variable quantities change with time or another reference value. It has also been called "the basic instrument of [physical science](/wiki/Physical_science)".

In the late 17th century, [Isaac Newton](/wiki/Isaac_Newton) and [Gottfried Wilhelm Leibniz](/wiki/Gottfried_Wilhelm_Leibniz) each independently formulated infinitesimal calculus. Later work, including the [formalization of the concept of limits](/wiki/(%CE%B5,_%CE%B4)-definition_of_limit), put calculus on a more solid conceptual footing. The concepts and techniques of calculus have broad applications in [science](/wiki/Science), [engineering](/wiki/Engineering), and other branches of mathematics.

## Etymology

In [Latin](/wiki/Latin), the word [*calculus*](https://en.wiktionary.org/wiki/calculus#Latin) means "pebble" – a meaning which still [persists in medicine](/wiki/Calculus_(medicine)). Because pebbles were used as counters in Roman counting-board [abacuses](/wiki/Abacus), Romans called their reckoning "placing pebbles" (*calculos ponere*), and would settle accounts by "calling someone to the pebbles" (*vocare aliquem ad calculos*); the Latin word *calculare* appeared around 400 AD in Spain. The word *calculate* was used in English in this sense at least as early as 1672, several years before the publications of Leibniz and Newton, who wrote their mathematical texts in Latin.

In addition to differential calculus and integral calculus, the term is also used for naming specific methods of computation or theories that imply some sort of computation. Examples of this usage include [propositional calculus](/wiki/Propositional_calculus), [Ricci calculus](/wiki/Ricci_calculus), [calculus of variations](/wiki/Calculus_of_variations), [lambda calculus](/wiki/Lambda_calculus), [sequent calculus](/wiki/Sequent_calculus), and [process calculus](/wiki/Process_calculus). Furthermore, the term *calculus* has variously been applied in ethics and philosophy, for such systems as [Bentham's](/wiki/Jeremy_Bentham) [felicific calculus](/wiki/Felicific_calculus), and the [ethical calculus](/wiki/Ethical_calculus).

## Primary concepts and basic notation

Calculus provides a generalization of concepts from elementary [geometry](/wiki/Geometry) and [algebra](/wiki/Algebra). For example, instead of describing the slope of a straight line, calculus can describe the changing slope of a complicated curve. Elementary geometry provides formulas for the area of shapes like [triangles](/wiki/Triangle), [squares](/wiki/Square), and other [polygons](/wiki/Polygon), whereas calculus provides a way to find the area of a shape whose boundary is a described by a complicated formula. In elementary algebra, one can calculate the distance traveled over time by an object moving at a constant [velocity](/wiki/Velocity), while in calculus, one can calculate the distance that an object travels even when the velocity varies.

### Limits and infinitesimals

Main articles: [Limit of a function](/wiki/Limit_of_a_function) and [Infinitesimal](/wiki/Infinitesimal)

Calculus is usually developed by working with very small quantities. Historically, the first method of doing so was by [infinitesimals](/wiki/Infinitesimal). These are objects which can be treated like real numbers but which are, in some sense, "infinitely small". For example, an infinitesimal number could be greater than 0, but less than any number in the sequence 1, 1/2, 1/3, ... and thus less than any positive [real number](/wiki/Real_number). From this point of view, calculus is a collection of techniques for manipulating infinitesimals.

| x {\displaystyle x} | sin ⁡ x x {\displaystyle {\frac {\sin x}{x}}} |
| --- | --- |
| 1 | 0.841471... |
| 0.1 | 0.998334... |
| 0.01 | 0.999983... |

Suppose there is a function, like the ratio ⁠

sin
⁡
x
x
{\displaystyle {\tfrac {\sin x}{x}}}
⁠, which cannot be defined at zero. However, as x becomes closer and closer to zero, ⁠

sin
⁡
x
x
{\displaystyle {\tfrac {\sin x}{x}}}
⁠ becomes arbitrarily close to 1. In other words, the limit of ⁠

sin
⁡
x
x
,
{\displaystyle {\tfrac {\sin x}{x}},}
⁠ as x approaches zero, equals 1.

The infinitesimal approach fell out of favor in the 19th century because it was difficult to make the notion of an infinitesimal precise. In the late 19th century, infinitesimals were replaced within academia by the [epsilon, delta](/wiki/Epsilon,_delta) approach to [limits](/wiki/Limit_of_a_function). Limits describe the behavior of a [function](/wiki/Function_(mathematics)) at a certain input in terms of its values at nearby inputs. They capture small-scale behavior using the intrinsic structure of the [real number system](/wiki/Real_number). In this treatment, calculus is a collection of techniques for manipulating certain limits. Infinitesimals get replaced by sequences of smaller and smaller numbers, and the infinitely small behavior of a function is found by taking the limiting behavior for these sequences. Limits were thought to provide a more rigorous foundation for calculus, and for this reason, they became the standard approach during the 20th century. However, the infinitesimal concept was revived in the 20th century with the introduction of [non-standard analysis](/wiki/Non-standard_analysis) and [smooth infinitesimal analysis](/wiki/Smooth_infinitesimal_analysis), which provided solid foundations for the manipulation of infinitesimals.

### Differential calculus

Main article: [Differential calculus](/wiki/Differential_calculus)

Tangent line at (*x*0, *f*(*x*0)). The derivative *f′*(*x*) of a curve at a point is the slope (rise over run) of the line tangent to that curve at that point.

Differential calculus is the study of the definition, properties, and applications of the [derivative](/wiki/Derivative) of a function. The process of finding the derivative is called *differentiation*. Given a function and a point in the domain, the derivative at that point is a way of encoding the small-scale behavior of the function near that point. By finding the derivative of a function at every point in its domain, it is possible to produce a new function, called the *derivative function* or just the *derivative* of the original function. Geometrically speaking, the derivative generalizes the idea of the slope of a line: it gives a way to quantify the steepness of the graph of a function, even when that graph is not a straight line.

In [Lagrange's notation](/wiki/Lagrange%27s_notation), the symbol for a derivative is an [apostrophe](/wiki/Apostrophe)-like mark called a [prime](/wiki/Prime_(symbol)). Thus, the derivative of a function called *f* is denoted by *f′*, pronounced "f prime" or "f dash". For instance, if *f*(*x*) = *x*2 is the squaring function, then *f′*(*x*) = 2*x* is its derivative.

If a function is [linear](/wiki/Linear_function) (that is if the [graph](/wiki/Graph_of_a_function) of the function is a straight line), then the function can be written as *y* = *mx* + *b*, where *x* is the independent variable, *y* is the dependent variable, *b* is the *y*-intercept, and:

:   m
    =

    rise
    run
    =

    change in 
    y

    change in 
    x
    =

    Δ
    y

    Δ
    x
    .
    {\displaystyle m={\frac {\text{rise}}{\text{run}}}={\frac {{\text{change in }}y}{{\text{change in }}x}}={\frac {\Delta y}{\Delta x}}.}

This gives an exact value for the slope of a straight line. If the graph of the function is not a straight line, however, then the change in *y* divided by the change in *x* varies. Derivatives give an exact meaning to the notion of change in output concerning change in input. To be concrete, let *f* be a function, and fix a point *a* in the domain of *f*. (*a*, *f*(*a*)) is a point on the graph of the function. If *h* is a number close to zero, then *a* + *h* is a number close to *a*. Therefore, (*a* + *h*, *f*(*a* + *h*)) is close to (*a*, *f*(*a*)). The slope between these two points is

:   m
    =

    f
    (
    a
    +
    h
    )
    −
    f
    (
    a
    )

    (
    a
    +
    h
    )
    −
    a
    =

    f
    (
    a
    +
    h
    )
    −
    f
    (
    a
    )
    h
    .
    {\displaystyle m={\frac {f(a+h)-f(a)}{(a+h)-a}}={\frac {f(a+h)-f(a)}{h}}.}

This expression is called a *[difference quotient](/wiki/Difference_quotient)*. A line through two points on a curve is called a *secant line*, so *m* is the slope of the secant line between (*a*, *f*(*a*)) and (*a* + *h*, *f*(*a* + *h*)). The secant line is only an approximation to the behavior of the function at the point  *a* because it does not account for what happens between  *a* and  *a* + *h*. It is not possible to discover the behavior at  *a* by setting *h* to zero because this would require [dividing by zero](/wiki/Dividing_by_zero), which is undefined. The derivative is defined by taking the [limit](/wiki/Limit_(mathematics)) as *h* tends to zero, meaning that it considers the behavior of *f* for all small values of *h* and extracts a consistent value for the case when *h* equals zero:

:   lim

    h
    →
    0

    f
    (
    a
    +
    h
    )
    −
    f
    (
    a
    )

    h
    .
    {\displaystyle \lim \_{h\to 0}{f(a+h)-f(a) \over {h}}.}

Geometrically, the derivative is the slope of the [tangent line](/wiki/Tangent_line) to the graph of *f* at *a*. The tangent line is a limit of secant lines just as the derivative is a limit of difference quotients.

If the input of the function represents time, then the derivative represents change concerning time. For example, if *f* is a function that takes time as input and gives the position of a ball at that time as output, then the derivative of *f* is how the position is changing in time, that is, it is the [velocity](/wiki/Velocity) of the ball.

### Leibniz notation

Main article: [Leibniz's notation](/wiki/Leibniz%27s_notation)

A common notation, introduced by Leibniz, for the derivative in the example above is

:   y

    =

    x

    2

    d
    y

    d
    x

    =
    2
    x
    .
    {\displaystyle {\begin{aligned}y&=x^{2}\\{\frac {dy}{dx}}&=2x.\end{aligned}}}

In an approach based on limits, the symbol ⁠*dy*/ *dx*⁠ is to be interpreted not as the quotient of two numbers but as a shorthand for the limit computed above. Leibniz, however, did intend it to represent the quotient of two infinitesimally small numbers, *dy* being the infinitesimally small change in *y* caused by an infinitesimally small change  *dx* applied to *x*. We can also think of ⁠*d*/ *dx*⁠ as a [differentiation operator](/wiki/Differentiation_operator), which takes a function as an input and gives another function, the derivative, as the output. For example:

:   d

    d
    x
    (

    x

    2
    )
    =
    2
    x
    .
    {\displaystyle {\frac {d}{dx}}(x^{2})=2x.}

In this usage, the *dx* in the denominator is read as "with respect to *x*". Another example of correct notation could be:

:   g
    (
    t
    )

    =

    t

    2
    +
    3
    t
    +
    1

    d

    d
    t
    g
    (
    t
    )

    =
    2
    t
    +
    3
    {\displaystyle {\begin{aligned}g(t)&=t^{2}+3t+1\\{d \over dt}g(t)&=2t+3\end{aligned}}}

### Integral calculus

Main article: [Integral](/wiki/Integral)

Integration can be thought of as measuring the area under a curve, defined by *f*(*x*), between two points (here  *a* and *b*).

A sequence of midpoint Riemann sums over a regular partition of an interval: the total area of the rectangles converges to the integral of the function.

*Integral calculus* is the study of the definitions, properties, and applications of two related concepts, the *indefinite integral* and the *definite integral*. The process of finding the value of an integral is called *integration*. The indefinite integral, also known as the *[antiderivative](/wiki/Antiderivative)*, is the inverse operation to the derivative. *F* is an indefinite integral of *f* when *f* is a derivative of *F*. (This use of lower- and upper-case letters for a function and its indefinite integral is common in calculus.) The definite integral inputs a function and outputs a number, which gives the algebraic sum of areas between the graph of the input and the [x-axis](/wiki/X-axis). The technical definition of the definite integral involves the [limit](/wiki/Limit_(mathematics)) of a sum of areas of rectangles, called a [Riemann sum](/wiki/Riemann_sum).

A motivating example is the distance traveled in a given time. If the speed is constant, only multiplication is needed:

:   D
    i
    s
    t
    a
    n
    c
    e
    =

    S
    p
    e
    e
    d
    ⋅

    T
    i
    m
    e
    {\displaystyle \mathrm {Distance} =\mathrm {Speed} \cdot \mathrm {Time} }

But if the speed changes, a more powerful method of finding the distance is necessary. One such method is to approximate the distance traveled by breaking up the time into many short intervals of time, then multiplying the time elapsed in each interval by one of the speeds in that interval, and then taking the sum (a [Riemann sum](/wiki/Riemann_sum)) of the approximate distance traveled in each interval. The basic idea is that if only a short time elapses, then the speed will stay more or less the same. However, a Riemann sum only gives an approximation of the distance traveled. We must take the limit of all such Riemann sums to find the exact distance traveled.

When velocity is constant, the total distance traveled over the given time interval can be computed by multiplying velocity and time. For example, traveling a steady 50 mph for 3 hours results in a total distance of 150 miles. Plotting the velocity as a function of time yields a rectangle with a height equal to the velocity and a width equal to the time elapsed. Therefore, the product of velocity and time also calculates the rectangular area under the (constant) velocity curve. This connection between the area under a curve and the distance traveled can be extended to *any* irregularly shaped region exhibiting a fluctuating velocity over a given period. If *f*(*x*) represents speed as it varies over time, the distance traveled between the times represented by  *a* and *b* is the area of the region between *f*(*x*) and the *x*-axis, between *x* = *a* and *x* = *b*.

To approximate that area, an intuitive method would be to divide up the distance between  *a* and *b* into several equal segments, the length of each segment represented by the symbol Δ*x*. For each small segment, we can choose one value of the function *f*(*x*). Call that value *h*. Then the area of the rectangle with base Δ*x* and height *h* gives the distance (time Δ*x* multiplied by speed *h*) traveled in that segment. Associated with each segment is the average value of the function above it, *f*(*x*) = *h*. The sum of all such rectangles gives an approximation of the area between the axis and the curve, which is an approximation of the total distance traveled. A smaller value for Δ*x* will give more rectangles and in most cases a better approximation, but for an exact answer, we need to take a limit as Δ*x* approaches zero.

The symbol of integration is

∫
{\displaystyle \int }
, an [elongated *S*](/wiki/Long_s) chosen to suggest summation. The definite integral is written as:

:   ∫

    a

    b
    f
    (
    x
    )

    d
    x
    {\displaystyle \int \_{a}^{b}f(x)\,dx}

and is read "the integral from *a* to *b* of *f*-of-*x* with respect to *x*." The Leibniz notation *dx* is intended to suggest dividing the area under the curve into an infinite number of rectangles so that their width Δ*x* becomes the infinitesimally small *dx*.

The indefinite integral, or antiderivative, is written:

:   ∫
    f
    (
    x
    )

    d
    x
    .
    {\displaystyle \int f(x)\,dx.}

Functions differing by only a constant have the same derivative, and it can be shown that the antiderivative of a given function is a family of functions differing only by a constant. Since the derivative of the function *y* = *x*2 + *C*, where *C* is any constant, is *y′* = 2*x*, the antiderivative of the latter is given by:

:   ∫
    2
    x

    d
    x
    =

    x

    2
    +
    C
    .
    {\displaystyle \int 2x\,dx=x^{2}+C.}

The unspecified constant *C* present in the indefinite integral or antiderivative is known as the [constant of integration](/wiki/Constant_of_integration).

### Fundamental theorem

Main article: [Fundamental theorem of calculus](/wiki/Fundamental_theorem_of_calculus)

The [fundamental theorem of calculus](/wiki/Fundamental_theorem_of_calculus) states that differentiation and integration are inverse operations. More precisely, it relates the values of antiderivatives to definite integrals. Because it is usually easier to compute an antiderivative than to apply the definition of a definite integral, the fundamental theorem of calculus provides a practical way of computing definite integrals. It can also be interpreted as a precise statement of the fact that differentiation is the inverse of integration.

The fundamental theorem of calculus states: If a function *f* is [continuous](/wiki/Continuous_function) on the interval [*a*, *b*] and if *F* is a function whose derivative is *f* on the interval (*a*, *b*), then

:   ∫

    a

    b
    f
    (
    x
    )

    d
    x
    =
    F
    (
    b
    )
    −
    F
    (
    a
    )
    .
    {\displaystyle \int \_{a}^{b}f(x)\,dx=F(b)-F(a).}

Furthermore, for every *x* in the interval (*a*, *b*),

:   d

    d
    x

    ∫

    a

    x
    f
    (
    t
    )

    d
    t
    =
    f
    (
    x
    )
    .
    {\displaystyle {\frac {d}{dx}}\int \_{a}^{x}f(t)\,dt=f(x).}

This realization, made by both [Newton](/wiki/Isaac_Newton) and [Leibniz](/wiki/Gottfried_Leibniz), was key to the proliferation of analytic results after their work became known. (The extent to which Newton and Leibniz were influenced by immediate predecessors, and particularly what Leibniz may have learned from the work of [Isaac Barrow](/wiki/Isaac_Barrow), is difficult to determine because of the priority dispute between them.) The fundamental theorem provides an algebraic method of computing many definite integrals—without performing limit processes—by finding formulae for [antiderivatives](/wiki/Antiderivative). It is also a prototype solution of a [differential equation](/wiki/Differential_equation). Differential equations relate an unknown function to its derivatives and are ubiquitous in the sciences.

## Advanced topics

### Multivariable and vector calculus

Main articles: [Multivariable calculus](/wiki/Multivariable_calculus) and [vector calculus](/wiki/Vector_calculus)

[Multivariable calculus](/wiki/Multivariable_calculus) is the extension of calculus in one variable to [functions of several variables](/wiki/Function_of_several_real_variables): the differentiation and integration of functions involving multiple variables (*[multivariate](/wiki/Multivariate_(mathematics))*), rather than just one.

[Vector calculus](/wiki/Vector_calculus) is a branch of multivariable calculus concerned with the differentiation and integration of [vector fields](/wiki/Vector_field), primarily in three-dimensional [Euclidean space](/wiki/Euclidean_space),

R

3
.
{\displaystyle \mathbb {R} ^{3}.}
 (The term *vector calculus* is sometimes used as a synonym for the broader subject of multivariable calculus overall.) Vector calculus plays an important role in [differential geometry](/wiki/Differential_geometry) and in the study of [partial differential equations](/wiki/Partial_differential_equation). It is used extensively in physics and engineering, especially in the description of [electromagnetic fields](/wiki/Electromagnetic_field), [gravitational fields](/wiki/Gravitational_field), and [fluid flow](/wiki/Fluid_flow).

### Differential equations

Main article: [Differential equation](/wiki/Differential_equation)

A [differential equation](/wiki/Differential_equation) is an [equation](/wiki/Functional_equation) that relates one or more unknown functions and their derivatives. In applications, the functions generally represent physical quantities, the derivatives represent their rates of change, and the differential equation defines a relationship between the two. Such relations are common in [mathematical models](/wiki/Mathematical_model) and [scientific laws](/wiki/Scientific_law); therefore, differential equations play a prominent role in many disciplines including [engineering](/wiki/Engineering), [physics](/wiki/Physics), [economics](/wiki/Economics), and [biology](/wiki/Biology).

For example, the differential equation

d
f

d
t
=
−
a
f
(
t
)
{\displaystyle {\frac {df}{dt}}=-af(t)}
is solved by a function

f
(
t
)
{\displaystyle f(t)}
 that is proportional to its own derivative. Any such function has the form

f
(
t
)
=
C

e

−
a
t
,
{\displaystyle f(t)=Ce^{-at},}
where

C
{\displaystyle C}
 is a constant. This differential equation describes [exponential decay](/wiki/Exponential_decay).

The study of differential equations consists mainly of the study of their solutions (the set of functions that satisfy each equation), and of the properties of their solutions. Only the simplest differential equations are solvable by explicit formulas; however, many properties of solutions of a given differential equation may be determined without computing them exactly, and differential equations that cannot be solved exactly are often amenable to numerical approximations.

### Real analysis

Main article: [Real analysis](/wiki/Real_analysis)

[Real analysis](/wiki/Real_analysis) provides the rigorous underpinnings of calculus, establishing that ideas often introduced heuristically in introductory calculus have a solid foundation. It studies the behavior of [real numbers](/wiki/Real_number), [sequences](/wiki/Sequence) and [series](/wiki/Series_(mathematics)) of real numbers, and [real functions](/wiki/Real_function). Some particular properties of real-valued sequences and functions that real analysis studies include [convergence](/wiki/Convergent_series), limits, [continuity](/wiki/Continuous_function), [smoothness](/wiki/Smoothness), differentiability, and integrability.

### Complex analysis

Main article: [Complex analysis](/wiki/Complex_analysis)

[Complex analysis](/wiki/Complex_analysis) investigates functions of a [complex](/wiki/Complex_number) variable. It is helpful in many branches of mathematics, including real analysis, [algebraic geometry](/wiki/Algebraic_geometry), [number theory](/wiki/Number_theory), [analytic combinatorics](/wiki/Analytic_combinatorics), and [applied mathematics](/wiki/Applied_mathematics), as well as in physics, including the branches of [hydrodynamics](/wiki/Hydrodynamics), [thermodynamics](/wiki/Thermodynamics), [quantum mechanics](/wiki/Quantum_mechanics), and [twistor theory](/wiki/Twistor_theory). By extension, use of complex analysis also has applications in engineering fields such as [nuclear](/wiki/Nuclear_engineering), [aerospace](/wiki/Aerospace_engineering), [mechanical](/wiki/Mechanical_engineering) and [electrical engineering](/wiki/Electrical_engineering).

The derivative of a function

f
{\displaystyle f}
 of a complex variable

z
{\displaystyle z}
 can be defined just as in elementary calculus:

d
f

d
z
=

lim

Δ
z
→
0

f
(
z
+
Δ
z
)
−
f
(
z
)

Δ
z
.
{\displaystyle {\frac {df}{dz}}=\lim \_{\Delta z\to 0}{\frac {f(z+\Delta z)-f(z)}{\Delta z}}.}
Because the limit

Δ
z
→
0
{\displaystyle \Delta z\to 0}
 can be taken along any direction in the complex plane, the condition of differentiability is more restrictive for functions of a complex variable than it is for functions of a real variable. Complex analysis studies [holomorphic functions](/wiki/Holomorphic_functions), the [differentiable functions](/wiki/Differentiable_function) of a complex variable. By contrast with the real case, a holomorphic function is always [infinitely differentiable](/wiki/Infinitely_differentiable) and equal to the sum of its [Taylor series](/wiki/Taylor_series) in some [neighborhood](/wiki/Neighborhood_(mathematics)) of each point of its [domain](/wiki/Domain_of_a_function). This makes methods and results of complex analysis significantly different from those of real analysis.

### Calculus of variations

Main article: [Calculus of variations](/wiki/Calculus_of_variations)

The [calculus of variations](/wiki/Calculus_of_variations) (or *variational calculus*) studies [functionals](/wiki/Functional_(mathematics)) in analogy to how elementary calculus studies functions. Whereas elementary calculus considers infinitesimally small changes in the input and output values of functions, the calculus of variations considers infinitesimally small changes in functions themselves. A functional is a [mapping](/wiki/Map_(mathematics)) from a set of functions to the real numbers. The calculus of variations studies how the output of a functional changes as the input function is infinitesimally perturbed.

A simple example of such a problem is to find the curve of shortest length connecting two points. If there are no constraints, the solution is a [straight line](/wiki/Straight_line) between the points. However, if the curve is constrained to lie on a surface in space, then the solution is less obvious, and possibly many solutions may exist. Such solutions are known as *[geodesics](/wiki/Geodesic)*. A related problem is posed by [Fermat's principle](/wiki/Fermat%27s_principle): light follows the path of shortest [optical length](/wiki/Optical_length) connecting two points, which depends upon the material of the medium. One corresponding concept in [mechanics](/wiki/Mechanics) is the [principle of least/stationary action](/wiki/Principle_of_least_action).

Functionals are often expressed as [definite integrals](/wiki/Definite_integral) involving functions and their [derivatives](/wiki/Derivative). Functions that maximize or minimize functionals may be found using the [Euler–Lagrange equation](/wiki/Euler%E2%80%93Lagrange_equation) of the calculus of variations.

## History

Main article: [History of calculus](/wiki/History_of_calculus)

Modern calculus was developed in 17th-century Europe by [Isaac Newton](/wiki/Isaac_Newton) and [Gottfried Wilhelm Leibniz](/wiki/Gottfried_Wilhelm_Leibniz) (independently of each other, first publishing around the same time). Elements of it first appeared in ancient Egypt and later Greece, then in China and the Middle East, and still later again in medieval Europe and India.

### Ancient precursors

#### Egypt and Babylon

Calculations of [volume](/wiki/Volume) and [area](/wiki/Area), one goal of integral calculus, can be found in the [Egyptian](/wiki/Egyptian_mathematics) [Moscow papyrus](/wiki/Moscow_Mathematical_Papyrus) (c. 1820 BC), but the formulae are simple instructions, with no indication as to how they were obtained. [Babylonians](/wiki/Babylon) may have discovered the [trapezoidal rule](/wiki/Trapezoidal_rule) while doing astronomical observations of [Jupiter](/wiki/Jupiter).

#### Greece

See also: [Greek mathematics](/wiki/Greek_mathematics)

Archimedes used the [method of exhaustion](/wiki/Method_of_exhaustion) to calculate the area under a parabola in his work *[Quadrature of the Parabola](/wiki/Quadrature_of_the_Parabola)*.

Laying the foundations for integral calculus and foreshadowing the concept of the limit, ancient Greek mathematician [Eudoxus of Cnidus](/wiki/Eudoxus_of_Cnidus) (c. 390–337 BC) developed the [method of exhaustion](/wiki/Method_of_exhaustion) to prove the formulas for cone and pyramid volumes.

During the [Hellenistic period](/wiki/Hellenistic_period), this method was further developed by [Archimedes](/wiki/Archimedes) (c. 287 – c. 212 BC), who combined it with a concept of the [indivisibles](/wiki/Cavalieri%27s_principle)—a precursor to [infinitesimals](/wiki/Archimedes_use_of_infinitesimals)—allowing him to solve several problems now treated by integral calculus. In *[The Method of Mechanical Theorems](/wiki/The_Method_of_Mechanical_Theorems)* he describes, for example, calculating the [center of gravity](/wiki/Center_of_gravity) of a solid [hemisphere](/wiki/Sphere), the center of gravity of a [frustum](/wiki/Frustum) of a circular [paraboloid](/wiki/Paraboloid), and the area of a region bounded by a [parabola](/wiki/Parabola) and one of its [secant lines](/wiki/Secant_line).

#### China

The method of exhaustion was later discovered independently in [China](/wiki/Chinese_mathematics) by [Liu Hui](/wiki/Liu_Hui) in the 3rd century AD to find the area of a circle. In the 5th century AD, [Zu Gengzhi](/wiki/Zu_Gengzhi), son of [Zu Chongzhi](/wiki/Zu_Chongzhi), established a method that would later be called [Cavalieri's principle](/wiki/Cavalieri%27s_principle) to find the volume of a [sphere](/wiki/Sphere).

### Medieval

#### Middle East

[Ibn al-Haytham](/wiki/Ibn_al-Haytham), 11th-century Arab mathematician and physicist

Indian mathematician and astronomer [Bhāskara II](/wiki/Bh%C4%81skara_II)

In the Middle East, [Hasan Ibn al-Haytham](/wiki/Ibn_al-Haytham), Latinized as Alhazen (c. 965 – c. 1040 AD) derived a formula for the sum of [fourth powers](/wiki/Fourth_power). He used the results to carry out what would now be called an [integration](/wiki/Integral) of this function, where the formulae for the sums of integral squares and fourth powers allowed him to calculate the volume of a [paraboloid](/wiki/Paraboloid).

#### India

[Bhāskara II](/wiki/Bh%C4%81skara_II) (c. 1114–1185) was acquainted with some ideas of differential calculus and suggested that the "differential coefficient" vanishes at an extremum value of the function.

In the 14th century, Indian mathematicians gave a non-rigorous method, resembling differentiation, applicable to some trigonometric functions. [Madhava of Sangamagrama](/wiki/Madhava_of_Sangamagrama) and the [Kerala School of Astronomy and Mathematics](/wiki/Kerala_School_of_Astronomy_and_Mathematics) stated components of calculus. According to [Victor J. Katz](/wiki/Victor_J._Katz), they, however, were not able to "combine many differing ideas under the two unifying themes of the [derivative](/wiki/Derivative) and the [integral](/wiki/Integral), show the connection between the two, and turn calculus into the great problem-solving tool we have today."

#### Europe

The mathematical study of continuity was revived in the 14th century by the [Oxford Calculators](/wiki/Oxford_Calculators) and French collaborators such as [Nicole Oresme](/wiki/Nicole_Oresme), who proved the divergence of the [harmonic series](/wiki/Harmonic_series_(mathematics)); both are also credited with formulating the [mean speed theorem](/wiki/Mean_speed_theorem).

### Modern

[Johannes Kepler](/wiki/Johannes_Kepler)'s work *Stereometria Doliorum* (1615) formed the basis of integral calculus. Kepler developed a method to calculate the area of an ellipse by adding up the lengths of many radii drawn from a focus of the ellipse. [Bonaventura Cavalieri](/wiki/Bonaventura_Cavalieri), basing his work on Kepler's, argued that volumes and areas should be computed as the sums of the volumes and areas of infinitesimally thin cross-sections.

The formal study of calculus brought together Cavalieri's infinitesimals with the [calculus of finite differences](/wiki/Calculus_of_finite_differences) developed in Europe at around the same time. [Pierre de Fermat](/wiki/Pierre_de_Fermat), claiming that he borrowed from [Diophantus](/wiki/Diophantus), introduced the concept of [adequality](/wiki/Adequality), which represented equality up to an infinitesimal error term. The combination was achieved by [John Wallis](/wiki/John_Wallis), [Isaac Barrow](/wiki/Isaac_Barrow), and [James Gregory](/wiki/James_Gregory_(astronomer_and_mathematician)), the latter two proving part of the [fundamental theorem of calculus](/wiki/Fundamental_theorem_of_calculus) around 1670.

The [product rule](/wiki/Product_rule) and [chain rule](/wiki/Chain_rule), the notions of [higher derivatives](/wiki/Higher_derivative) and [Taylor series](/wiki/Taylor_series), and of [analytic functions](/wiki/Analytic_function) were used by [Isaac Newton](/wiki/Isaac_Newton) in an idiosyncratic notation which he applied to solve problems of [mathematical physics](/wiki/Mathematical_physics). In his works, Newton rephrased his ideas to suit the mathematical idiom of the time, replacing calculations with infinitesimals by equivalent geometrical arguments that were considered beyond reproach. He used the methods of calculus to solve the problem of planetary motion, the shape of the surface of a rotating fluid, the oblateness of the earth, the motion of a weight sliding on a [cycloid](/wiki/Cycloid), and many other problems discussed in his *[Principia Mathematica](/wiki/Philosophi%C3%A6_Naturalis_Principia_Mathematica)* (1687). In other work, he developed series expansions for functions, including fractional and irrational powers, and it was clear that he understood the principles of the [Taylor series](/wiki/Taylor_series). He did not publish all these discoveries, and at this time, infinitesimal methods were still considered disreputable.

[Gottfried Wilhelm Leibniz](/wiki/Gottfried_Wilhelm_Leibniz) was the first to state clearly the rules of calculus.

[Isaac Newton](/wiki/Isaac_Newton) developed the use of calculus in his [laws of motion](/wiki/Newton%27s_laws_of_motion) and [universal gravitation](/wiki/Newton%27s_law_of_universal_gravitation).

These ideas were arranged into a true calculus of infinitesimals by [Gottfried Wilhelm Leibniz](/wiki/Gottfried_Wilhelm_Leibniz), who was originally accused of [plagiarism](/wiki/Plagiarism) by Newton. He is now regarded as an [independent inventor](/wiki/Multiple_discovery) of and contributor to calculus. His contribution was to provide a clear set of rules for working with infinitesimal quantities, allowing the computation of second and higher derivatives, and providing the [product rule](/wiki/Product_rule) and [chain rule](/wiki/Chain_rule), in their differential and integral forms. Unlike Newton, Leibniz put painstaking effort into his choices of notation.

Today, Leibniz and Newton are usually both given credit for independently inventing and developing calculus. Newton was the first to apply calculus to general [physics](/wiki/Physics). Leibniz developed much of the notation used in calculus today. The basic insights that both Newton and Leibniz provided led to their development of the laws of differentiation and integration, their emphasis that differentiation and integration are inverse processes, their development of methods for calculating the second and higher derivatives, and their statement of the notion for approximating a polynomial series.

When Newton and Leibniz first published their results, there was [great controversy](/wiki/Newton_v._Leibniz_calculus_controversy) over which mathematician (and therefore which country) deserved credit. Newton derived his results first (later to be published in his *[Method of Fluxions](/wiki/Method_of_Fluxions)*), but Leibniz published his "[Nova Methodus pro Maximis et Minimis](/wiki/Nova_Methodus_pro_Maximis_et_Minimis)" first. Newton claimed Leibniz stole ideas from his unpublished notes, which Newton had shared with a few members of the [Royal Society](/wiki/Royal_Society). This controversy divided English-speaking mathematicians from continental European mathematicians for many years, to the detriment of English mathematics. A careful examination of the papers of Leibniz and Newton shows that they arrived at their results independently, with Leibniz starting first with integration and Newton with differentiation. It is Leibniz, however, who gave the new discipline its name. Newton called his calculus "[the science of fluxions](/wiki/Method_of_fluxions)", a term that endured in English schools into the 19th century. The first complete treatise on calculus to be written in English and use the Leibniz notation was not published until 1815.

[Maria Gaetana Agnesi](/wiki/Maria_Gaetana_Agnesi)

Since the time of Leibniz and Newton, many mathematicians have contributed to the continuing development of calculus. One of the first and most complete works on both infinitesimal and [integral calculus](/wiki/Integral_calculus) was written in 1748 by [Maria Gaetana Agnesi](/wiki/Maria_Gaetana_Agnesi).

### Foundations

In calculus, *foundations* refers to the [rigorous](/wiki/Rigorous#Mathematical_rigor) development of the subject from [axioms](/wiki/Axiom) and definitions. In early calculus, the use of [infinitesimal](/wiki/Infinitesimal) quantities was thought unrigorous and was fiercely criticized by several authors, most notably [Michel Rolle](/wiki/Michel_Rolle) and [Bishop Berkeley](/wiki/George_Berkeley). Berkeley famously described infinitesimals as the [ghosts of departed quantities](/wiki/Ghosts_of_departed_quantities) in his book *[The Analyst](/wiki/The_Analyst)* in 1734. Working out a rigorous foundation for calculus occupied mathematicians for much of the century following Newton and Leibniz.

Several mathematicians, including [Maclaurin](/wiki/Colin_Maclaurin), tried to prove the soundness of using infinitesimals, but it would not be until 150 years later when, due to the work of [Cauchy](/wiki/Augustin-Louis_Cauchy) and [Weierstrass](/wiki/Karl_Weierstrass), a way was finally found to avoid mere "notions" of infinitely small quantities. The foundations of differential and integral calculus had been laid. In Cauchy's *[Cours d'Analyse](/wiki/Cours_d%27Analyse)*, we find a broad range of foundational approaches, including a definition of [continuity](/wiki/Continuous_function) in terms of infinitesimals, and a (somewhat imprecise) prototype of an [(ε, δ)-definition of limit](/wiki/(%CE%B5,_%CE%B4)-definition_of_limit) in the definition of differentiation. In his work, Weierstrass formalized the concept of [limit](/wiki/Limit_of_a_function) and eliminated infinitesimals (although his definition can validate [nilsquare](/wiki/Nilsquare) infinitesimals). Following the work of Weierstrass, it eventually became common to base calculus on limits instead of infinitesimal quantities, though the subject is still occasionally called "infinitesimal calculus". [Bernhard Riemann](/wiki/Bernhard_Riemann) used these ideas to give a precise definition of the integral. It was also during this period that the ideas of calculus were generalized to the [complex plane](/wiki/Complex_plane) with the development of [complex analysis](/wiki/Complex_analysis).

In modern mathematics, the foundations of calculus are included in the field of [real analysis](/wiki/Real_analysis), which contains full definitions and [proofs](/wiki/Mathematical_proof) of the theorems of calculus. The reach of calculus has also been greatly extended. [Henri Lebesgue](/wiki/Henri_Lebesgue) invented [measure theory](/wiki/Measure_theory), based on earlier developments by [Émile Borel](/wiki/%C3%89mile_Borel), and used it to define integrals of all but the most [pathological](/wiki/Pathological_(mathematics)) functions. [Laurent Schwartz](/wiki/Laurent_Schwartz) introduced [distributions](/wiki/Distribution_(mathematics)), which can be used to take the derivative of any function whatsoever.

Limits are not the only rigorous approach to the foundation of calculus. Another way is to use [Abraham Robinson](/wiki/Abraham_Robinson)'s [non-standard analysis](/wiki/Non-standard_analysis). Robinson's approach, developed in the 1960s, uses technical machinery from [mathematical logic](/wiki/Mathematical_logic) to augment the real number system with [infinitesimal](/wiki/Infinitesimal) and [infinite](/wiki/Infinity) numbers, as in the original Newton-Leibniz conception. The resulting numbers are called [hyperreal numbers](/wiki/Hyperreal_number), and they can be used to give a Leibniz-like development of the usual rules of calculus. There is also [smooth infinitesimal analysis](/wiki/Smooth_infinitesimal_analysis), which differs from non-standard analysis in that it mandates neglecting higher-power infinitesimals during derivations. Based on the ideas of [F. W. Lawvere](/wiki/F._W._Lawvere) and employing the methods of [category theory](/wiki/Category_theory), smooth infinitesimal analysis views all functions as being [continuous](/wiki/Continuous_function) and incapable of being expressed in terms of [discrete](/wiki/Discrete_mathematics) entities. One aspect of this formulation is that the [law of excluded middle](/wiki/Law_of_excluded_middle) does not hold. The law of excluded middle is also rejected in [constructive mathematics](/wiki/Constructive_mathematics), a branch of mathematics that insists that proofs of the existence of a number, function, or other mathematical object should give a construction of the object. Reformulations of calculus in a constructive framework are generally part of the subject of [constructive analysis](/wiki/Constructive_analysis).

### Significance

While many of the ideas of calculus had been developed earlier in [Greece](/wiki/Greek_mathematics), [China](/wiki/Chinese_mathematics), [India](/wiki/Indian_mathematics), [Iraq, Persia](/wiki/Islamic_mathematics), and [Japan](/wiki/Japanese_mathematics), the use of calculus began in Europe, during the 17th century, when Newton and Leibniz built on the work of earlier mathematicians to introduce its basic principles. The Hungarian polymath [John von Neumann](/wiki/John_von_Neumann) wrote of this work,

> The calculus was the first achievement of modern mathematics and it is difficult to overestimate its importance. I think it defines more unequivocally than anything else the inception of modern mathematics, and the system of mathematical analysis, which is its logical development, still constitutes the greatest technical advance in exact thinking.

Applications of differential calculus include computations involving [velocity](/wiki/Velocity) and [acceleration](/wiki/Acceleration), the [slope](/wiki/Slope) of a curve, and [optimization](/wiki/Mathematical_optimization). Applications of integral calculus include computations involving area, [volume](/wiki/Volume), [arc length](/wiki/Arc_length), [center of mass](/wiki/Center_of_mass), [work](/wiki/Work_(physics)), and [pressure](/wiki/Pressure). More advanced applications include [power series](/wiki/Power_series) and [Fourier series](/wiki/Fourier_series).

Calculus is also used to gain a more precise understanding of the nature of space, time, and motion. For centuries, mathematicians and philosophers wrestled with paradoxes involving [division by zero](/wiki/Division_by_zero) or sums of infinitely many numbers. These questions arise in the study of [motion](/wiki/Motion_(physics)) and area. The [ancient Greek](/wiki/Ancient_Greek) philosopher [Zeno of Elea](/wiki/Zeno_of_Elea) gave several famous examples of such [paradoxes](/wiki/Zeno%27s_paradoxes). Calculus provides tools, especially the [limit](/wiki/Limit_(mathematics)) and the [infinite series](/wiki/Infinite_series), that resolve the paradoxes.

## Applications

The [logarithmic spiral](/wiki/Logarithmic_spiral) of the [nautilus shell](/wiki/Nautilus) is a classical image used to depict the growth and change related to calculus.

Calculus is used in every branch of the physical sciences, [actuarial science](/wiki/Actuarial_science), [computer science](/wiki/Computer_science), [statistics](/wiki/Statistics), [engineering](/wiki/Engineering), [economics](/wiki/Economics), [business](/wiki/Business), [medicine](/wiki/Medicine), [demography](/wiki/Demography), and in other fields wherever a problem can be [mathematically modeled](/wiki/Mathematical_model) and an [optimal](/wiki/Optimization_(mathematics)) solution is desired. It allows one to go from (non-constant) rates of change to the total change or vice versa, and many times in studying a problem we know one and are trying to find the other. Calculus can be used in conjunction with other mathematical disciplines. For example, it can be used with [linear algebra](/wiki/Linear_algebra) to find the "best fit" linear approximation for a set of points in a domain. Or, it can be used in [probability theory](/wiki/Probability_theory) to determine the [expectation value](/wiki/Expectation_value) of a continuous [random variable](/wiki/Random_variable) given a [probability density function](/wiki/Probability_density_function). In [analytic geometry](/wiki/Analytic_geometry), the study of graphs of functions, calculus is used to find high points and low points (maxima and minima), slope, [concavity](/wiki/Concave_function), [inflection points](/wiki/Inflection_points), area under curves, and area between curves. Calculus is also used to find approximate solutions to equations; in practice, it is the standard way to solve differential equations and do root finding in most applications. Examples are methods such as [Newton's method](/wiki/Newton%27s_method), [fixed point iteration](/wiki/Fixed_point_iteration), and [linear approximation](/wiki/Linear_approximation). For instance, spacecraft use a variation of the [Euler method](/wiki/Euler_method) to approximate curved courses within zero-gravity environments.

[Physics](/wiki/Physics) makes particular use of calculus; all concepts in [classical mechanics](/wiki/Classical_mechanics) and [electromagnetism](/wiki/Electromagnetism) are related through calculus. The [mass](/wiki/Mass) of an object of known [density](/wiki/Density), the [moment of inertia](/wiki/Moment_of_inertia) of objects, and the [potential energies](/wiki/Potential_energy) due to gravitational and electromagnetic forces can all be found by the use of calculus. An example of the use of calculus in mechanics is [Newton's second law of motion](/wiki/Newton%27s_laws_of_motion), which states that the derivative of an object's [momentum](/wiki/Momentum) concerning time equals the net [force](/wiki/Force) upon it. Alternatively, Newton's second law can be expressed by saying that the net force equals the object's mass times its [acceleration](/wiki/Acceleration), which is the time derivative of velocity and thus the second time derivative of spatial position. Starting from knowing how an object is accelerating, we use calculus to derive its path.

Maxwell's theory of [electromagnetism](/wiki/Electromagnetism) and [Einstein](/wiki/Albert_Einstein)'s theory of [general relativity](/wiki/General_relativity) are also expressed in the language of differential calculus. Differential equations are likewise prominent in [quantum mechanics](/wiki/Quantum_mechanics). Chemistry also uses calculus, for example in determining reaction rates and in studying radioactive decay. In biology, population dynamics starts with reproduction and death rates to model population changes.

In the realm of medicine, calculus can be used in many ways, from predicting the optimal branching angle of a [blood vessel](/wiki/Blood_vessel) to maximize flow, to understanding how quickly a drug is eliminated from a body or how quickly a [cancerous](/wiki/Cancer) tumor grows.

In economics, calculus allows for the determination of maximal profit by providing a way to easily calculate both [marginal cost](/wiki/Marginal_cost) and [marginal revenue](/wiki/Marginal_revenue). The [Black–Scholes model](/wiki/Black%E2%80%93Scholes_model), a central concept in [option pricing](/wiki/Option_(finance)), employs a differential equation.

## See also

Main article: [Outline of calculus](/wiki/Outline_of_calculus)

- [Glossary of calculus](/wiki/Glossary_of_calculus)
- [List of calculus topics](/wiki/List_of_calculus_topics)
- [List of derivatives and integrals in alternative calculi](/wiki/List_of_derivatives_and_integrals_in_alternative_calculi)
- [List of differentiation identities](/wiki/List_of_differentiation_identities)
- [Publications in calculus](/wiki/List_of_publications_in_mathematics#Calculus)
- [Table of integrals](/wiki/Table_of_integrals)
- [Real Analysis](/wiki/Real_Analysis)
- [Mathematical Analysis](/wiki/Mathematical_Analysis)

## References

## Further reading

## External links

- ["Calculus"](https://www.encyclopediaofmath.org/index.php?title=Calculus), *[Encyclopedia of Mathematics](/wiki/Encyclopedia_of_Mathematics)*, [EMS Press](/wiki/European_Mathematical_Society), 2001 [1994]
- [Weisstein, Eric W.](/wiki/Eric_W._Weisstein) ["Calculus"](https://mathworld.wolfram.com/Calculus.html). *[MathWorld](/wiki/MathWorld)*.
- [Topics on Calculus](https://planetmath.org/TopicsOnCalculus) at [PlanetMath](/wiki/PlanetMath).
- [Calculus Made Easy (1914) by Silvanus P. Thompson](http://djm.cc/library/Calculus_Made_Easy_Thompson.pdf) Full text in PDF
- [Calculus](https://www.bbc.co.uk/programmes/b00mrfwq) on [*In Our Time*](/wiki/In_Our_Time_(radio_series)) at the [BBC](/wiki/BBC)
- [Calculus.org: The Calculus page](http://www.calculus.org) at University of California, Davis – contains resources and links to other sites
- [Earliest Known Uses of Some of the Words of Mathematics: Calculus & Analysis](http://www.economics.soton.ac.uk/staff/aldrich/Calculus%20and%20Analysis%20Earliest%20Uses.htm)
- [The Role of Calculus in College Mathematics](http://www.ericdigests.org/pre-9217/calculus.htm) [Archived](https://web.archive.org/web/20210726234750/http://www.ericdigests.org/pre-9217/calculus.htm) 26 July 2021 at the [Wayback Machine](/wiki/Wayback_Machine) from ERICDigests.org
- [OpenCourseWare Calculus](https://ocw.mit.edu/courses/mathematics/18-01sc-single-variable-calculus-fall-2010/) from the [Massachusetts Institute of Technology](/wiki/Massachusetts_Institute_of_Technology)
- [Infinitesimal Calculus](http://www.encyclopediaofmath.org/index.php?title=Infinitesimal_calculus&oldid=18648) – an article on its historical development, in *Encyclopedia of Mathematics*, ed. [Michiel Hazewinkel](/wiki/Michiel_Hazewinkel).
- Daniel Kleitman, MIT. ["Calculus for Beginners and Artists"](http://math.mit.edu/~djk/calculus_beginners/).
- [Calculus training materials at imomath.com](http://www.imomath.com/index.php?options=277) [Archived](https://web.archive.org/web/20230709175857/https://www.imomath.com/index.php?options=277) 9 July 2023 at the [Wayback Machine](/wiki/Wayback_Machine)
- (in English and Arabic) [The Excursion of Calculus](http://www.wdl.org/en/item/4327/), 1772
