# Physics 1 Study Guide: Lectures 1-5

## Scope

This guide covers measurement and units, one-dimensional kinematics, motion
graphs, constant-acceleration equations, free fall, two-dimensional vectors,
and introductory two-dimensional kinematics. It is based on all 116 indexed
pages across Lectures 1-5.

## 1. Measurement, Units, and Models

### Physical models

Physics uses shared mathematical and conceptual tools to model many different
phenomena. The course begins with kinematics, which describes motion, before
moving to why motion occurs and how systems interact.
[Physics 1, Physics1_Lecture01_002.pdf, Page 18]

### Base and derived quantities

- The base quantities introduced here are length, time, and mass.
- Derived quantities combine base quantities. Velocity, for example, has units
  of length divided by time.
[Physics 1, Physics1_Lecture01_002.pdf, Page 19]

### Scientific notation and prefixes

- Scientific notation separates a coefficient from a power of ten:
  `3.0 x 10^8 m/s`.
- Metric prefixes are shorthand for powers of ten, such as kilo, milli, and
  micro.
- Preserve units during every algebraic step.
[Physics 1, Physics1_Lecture01_002.pdf, Pages 21-22]

### Conversion factors

Multiply by conversion factors equal to one so unwanted units cancel.

```math
3.0 \times 10^8\,\mathrm{m/s}\times\frac{1\,\mathrm{km}}{1000\,\mathrm{m}}=3.0\times10^5\,\mathrm{km/s}
```

For area, square the entire unit conversion. For volume, cube it.
[Physics 1, Physics1_Lecture01_002.pdf, Pages 23-26]

### Dimensional analysis

Every term added or subtracted in a valid physical equation must have the same
dimensions. Dimensional consistency can reject an impossible equation, but it
does not prove that a physically correct equation has been found.
[Physics 1, Physics1_Lecture01_002.pdf, Page 27]

## 2. Kinematics Foundations

Kinematics describes motion. In the initial one-dimensional treatment,
objects are modeled as particles.
[Physics 1, Physics1_Lecture02_002.pdf, Page 3]

### Scalars and vectors

- A scalar has magnitude only.
- A vector has both magnitude and direction.
- Vector arrows show direction, while arrow length represents magnitude.
- The magnitude of vector `v` is written `|v|`.
[Physics 1, Physics1_Lecture02_002.pdf, Pages 5-6]

### Position, displacement, and distance

- Position describes location relative to a chosen reference point.
- Displacement is the vector change in position:

```math
\Delta\vec{x}=\vec{x}_f-\vec{x}_i
```

- Distance is the scalar length of the path traveled.
- Distance and displacement have the same SI unit, meters, but they are not
  interchangeable.
[Physics 1, Physics1_Lecture02_002.pdf, Pages 4 and 7]

### Average velocity and average speed

```math
\vec{v}_{\mathrm{avg}}=\frac{\Delta\vec{x}}{\Delta t}
s_{\mathrm{avg}}=\frac{\mathrm{total\ distance}}{\Delta t}
```

Average velocity depends on displacement. A round trip can therefore have zero
average velocity while having a nonzero average speed.
[Physics 1, Physics1_Lecture02_002.pdf, Pages 10-11]

### Instantaneous velocity

Instantaneous velocity is the time derivative of position:

```math
\vec{v}(t)=\frac{d\vec{x}}{dt}
```

Instantaneous speed is the magnitude `|v|`. In one dimension, the sign of
velocity communicates direction.
[Physics 1, Physics1_Lecture02_002.pdf, Pages 15-16 and 21]

### Acceleration

Acceleration is the time rate of change of velocity:

```math
\vec{a}_{\mathrm{avg}}=\frac{\Delta\vec{v}}{\Delta t}
\vec{a}(t)=\frac{d\vec{v}}{dt}=\frac{d^2\vec{x}}{dt^2}
```

Its SI unit is `m/s^2`. Negative acceleration does not automatically mean an
object is slowing down. Speed changes according to the relationship between
the directions of velocity and acceleration.
[Physics 1, Physics1_Lecture02_002.pdf, Page 22]
[Physics 1, Physics1_Lecture03_002.pdf, Pages 1-2]

## 3. Reading Motion Graphs

### Slope rules

- Slope of a position-time graph gives velocity.
- The tangent slope gives instantaneous velocity.
- Slope of a velocity-time graph gives acceleration.
[Physics 1, Physics1_Lecture03_002.pdf, Pages 8-9 and 12]

### Area rules

- Area under a velocity-time graph gives displacement.
- Area under an acceleration-time graph gives change in velocity.
- Initial conditions are needed to recover an absolute velocity or position
  from those changes.
[Physics 1, Physics1_Lecture03_002.pdf, Page 14]

### Sign reasoning

Use velocity and acceleration signs together:

| Velocity | Acceleration | Motion |
|---|---|---|
| Same sign | Same direction | Speed increases |
| Opposite signs | Opposite directions | Speed decreases |
| `v = 0` | `a` may be nonzero | Possible turning point |

Interpreting a velocity-time graph requires considering both the direction of
velocity and the direction of acceleration.
[Physics 1, Physics1_Lecture03_002.pdf, Page 13]

## 4. Constant-Acceleration Motion

These equations apply only when acceleration is constant. Choose a coordinate
direction first and use positive and negative signs consistently.
[Physics 1, Physics1_Lecture04_002.pdf, Pages 7-8]

### Formula sheet

```math
v=v_0+at

\Delta x=v_0t+\frac{1}{2}at^2

v^2=v_0^2+2a\Delta x
```

Equation selection:

- No position in the problem: start with `v = v_0 + at`.
- Initial conditions and time are central: use
  `Delta x = v_0 t + (1/2)at^2`.
- Time is absent: use `v^2 = v_0^2 + 2a Delta x`.
[Physics 1, Physics1_Lecture04_002.pdf, Pages 9-12]

### Problem-solving workflow

1. Draw the situation at all important moments.
2. Choose an origin and a positive coordinate direction.
3. Label known positions, velocities, accelerations, and times.
4. List the unknowns.
5. Choose an equation containing the unknown and available known quantities.
6. Solve symbolically before substituting numbers.
7. Check units and whether the sign and magnitude are physically reasonable.

The first four steps come directly from the lecture's kinematics workflow.
[Physics 1, Physics1_Lecture04_002.pdf, Page 13]

## 5. Free Fall

An object is in free fall when gravity is its only acceleration. Near Earth's
surface:

```math
\vec{g}=9.8\,\mathrm{m/s^2}\quad\mathrm{(toward\ Earth's\ center)}
```

If upward is positive, use `a = -g`. If downward is positive, use `a = +g`.
The acceleration remains downward while an object rises, pauses at maximum
height, and falls. At maximum height, velocity is momentarily zero but
acceleration is not.
[Physics 1, Physics1_Lecture04_002.pdf, Page 19]
[Physics 1, Physics1_Lecture02_002.pdf, Pages 24-26]

Air resistance is ignored in the course's introductory free-fall problems.
The constant value `g = 9.8 m/s^2` is a near-Earth approximation.
[Physics 1, Physics1_Lecture04_002.pdf, Page 19]

## 6. Two-Dimensional Vectors

### Magnitude and direction

A 2D vector is represented by an arrow in a plane. Its length represents
magnitude and its orientation represents direction. Angles in the lecture are
typically measured counterclockwise from the positive x-axis.
[Physics 1, Physics1_Lecture05_002.pdf, Pages 7-8]

### Components

For a vector of magnitude `r` at angle `theta` measured counterclockwise from
the positive x-axis:

```math
r_x=r\cos\theta
r_y=r\sin\theta
\vec{r}=\langle r_x,r_y\rangle
```

Signs must agree with the vector's quadrant. The appropriate trigonometric
relationship depends on the coordinate system and angle definition.
[Physics 1, Physics1_Lecture05_002.pdf, Page 9]

Recover magnitude and direction with:

```math
|\vec{r}|=\sqrt{r_x^2+r_y^2}
\theta=\operatorname{atan2}(r_y,r_x)
```

Use `atan2`, or explicitly correct for the quadrant, rather than relying only
on `tan^-1(r_y/r_x)`.
[Physics 1, Physics1_Lecture05_002.pdf, Page 11]

### Unit vectors

The unit vectors `i`, `j`, and `k` point in the x, y, and z directions and
each has magnitude one:

```math
\vec{a}=a_x\hat{\imath}+a_y\hat{\jmath}
```

[Physics 1, Physics1_Lecture05_002.pdf, Page 13]

### Vector addition

- Graphically, place vectors tip to tail.
- Algebraically, add corresponding components:

```math
\vec{A}+\vec{B}=\langle A_x+B_x,A_y+B_y\rangle
```

- Vector addition is commutative.
- When vectors are given as magnitude and direction, convert to components,
  add components, then convert the result back if needed.
[Physics 1, Physics1_Lecture05_002.pdf, Pages 14-15]

### Position, velocity, and acceleration in 2D

```math
\vec{r}=\langle x,y\rangle
\Delta\vec{r}=\vec{r}_f-\vec{r}_i

\vec{v}_{\mathrm{avg}}=\frac{\Delta\vec{r}}{\Delta t}
\vec{v}=\frac{d\vec{r}}{dt}=\left\langle\frac{dx}{dt},\frac{dy}{dt}\right\rangle

\vec{a}_{\mathrm{avg}}=\frac{\Delta\vec{v}}{\Delta t}
\vec{a}=\frac{d\vec{v}}{dt}=\left\langle\frac{d^2x}{dt^2},\frac{d^2y}{dt^2}\right\rangle
```

The same derivative definitions used in one dimension apply independently to
each coordinate component.
[Physics 1, Physics1_Lecture05_002.pdf, Pages 20-22]

## 7. Common Exam Traps

1. **Distance versus displacement:** distance is path length; displacement
   depends only on initial and final positions.
2. **Speed versus velocity:** speed is scalar and nonnegative; velocity includes
   direction.
3. **Negative acceleration:** it does not always mean slowing down.
4. **Turning points:** `v = 0` does not imply `a = 0`.
5. **Graph confusion:** slope and area answer different questions.
6. **Kinematic equations:** do not use the constant-acceleration formulas when
   acceleration varies.
7. **Free-fall signs:** `g` is a positive magnitude; the coordinate choice
   determines the sign of `a`.
8. **Vector angles:** verify the quadrant after using inverse trigonometry.
9. **Area and volume conversions:** square or cube the conversion factor.

## 8. Practice Questions

1. Convert `3.0 x 10^8 m/s` to `km/s`.
2. A runner completes one lap and returns to the starting point. Compare the
   runner's distance, displacement, average speed, and average velocity.
3. If `x(t) = t^3 + 35 - 27t`, find `v(t)` and the positive time when the
   object changes direction.
4. If `y(t) = 2.0 + 15t - 4.9t^2`, find acceleration, time of maximum height,
   and maximum height.
5. Explain how to obtain velocity from a position-time graph and displacement
   from a velocity-time graph.
6. A ruler falls `0.14 m` from rest before being caught. Ignoring air
   resistance, estimate the reaction time.
7. A ball is dropped from rest. How fast is it moving after `4.0 s`, ignoring
   air resistance?
8. Find the components of a `24 m` vector at `65 degrees` counterclockwise from
   the positive x-axis.
9. Find the magnitude and direction of `<-7.2, 4.1> km`.
10. Add the displacement vectors `5i m`, `12 m at 165 degrees`, and `-12j m`.
    In which quadrant does the result point?

## 9. Answer Key

1. `3.0 x 10^5 km/s`.
   [Physics 1, Physics1_Lecture01_002.pdf, Page 23]
2. Distance and average speed are positive. Displacement and average velocity
   are zero because the final and initial positions are the same.
   [Physics 1, Physics1_Lecture02_002.pdf, Pages 7 and 10-11]
3. `v(t) = 3t^2 - 27`; the positive turning time is `t = 3 s`.
   [Physics 1, Physics1_Lecture02_002.pdf, Pages 13 and 17-19]
4. `a = -9.8 m/s^2`; `t_max = 15/9.8 = 1.53 s`; maximum height is about
   `13.5 m`.
   [Physics 1, Physics1_Lecture02_002.pdf, Pages 24-26]
5. Velocity is the tangent slope of the position-time graph. Displacement is
   the signed area under the velocity-time graph.
   [Physics 1, Physics1_Lecture03_002.pdf, Pages 9 and 14]
6. Use `Delta x = (1/2)gt^2`: `t = sqrt(2(0.14)/9.8) = 0.169 s`.
   [Physics 1, Physics1_Lecture04_002.pdf, Page 20]
7. `v = gt = 39.2 m/s` downward.
   [Physics 1, Physics1_Lecture05_002.pdf, Page 1]
8. `r_x = 24 cos(65 degrees) = 10.1 m`;
   `r_y = 24 sin(65 degrees) = 21.8 m`.
   [Physics 1, Physics1_Lecture05_002.pdf, Page 9]
9. Magnitude `= 8.3 km`; direction `= 150 degrees` counterclockwise from +x.
   [Physics 1, Physics1_Lecture05_002.pdf, Page 11]
10. The result is approximately `<-6.6, -8.9> m`, so it points into quadrant
    III.
    [Physics 1, Physics1_Lecture05_002.pdf, Page 16]

## 10. Source Coverage and Review Notes

All five lecture files were retrieved exhaustively:

- Lecture 1: 28 indexed pages
- Lecture 2: 27 indexed pages
- Lecture 3: 16 indexed pages
- Lecture 4: 23 indexed records corresponding to the PDF's slide sequence
- Lecture 5: 22 indexed pages

Five records were marked `review-needed`:

- Lecture 1, pages 23-24: native extractor disagreement
- Lecture 3, page 14: native extractor disagreement
- Lecture 4, page 16: no native text; handwritten solution
- Lecture 5, page 9: native extractor disagreement

The handwritten Lecture 4 page 16 was visually inspected. It sets up two
position equations for the red and green cars and solves the two-equation
system for the red car's acceleration. Formula-heavy claims from other flagged
pages should be checked against their rendered page before high-stakes use.
