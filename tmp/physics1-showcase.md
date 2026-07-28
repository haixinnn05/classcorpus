# Physics 1 Lectures 1-5

## Coverage And Review Notes

- Scope: all 116 indexed pages from the five supplied lecture PDFs.
- Native extraction initially marked five pages for review. Full-page renders were inspected, six visual descriptions were stored, and no records remain review-needed.
- Local Tesseract OCR completed for all 116 pages with no processing failures. OCR confidence is an uncalibrated signal, so visual descriptions take precedence for handwritten mathematics.
- The sequence moves from measurement and unit consistency to one-dimensional motion, graph interpretation, constant-acceleration models, and finally vectors and two-dimensional motion.

## Lecture Progression

### Lecture 1: Measurement, Units, And Consistency

Unit conversions work by multiplying by ratios equal to one so unwanted units cancel. The worked speed-of-light example converts meters per second to kilometers per second and then to miles per second, while preserving the appropriate significant figures. [Physics 1, Physics1_Lecture01_002.pdf, Page 24]

Dimensional analysis checks whether terms in an equation can be added or equated: every additive term must have compatible dimensions. [Physics 1, Physics1_Lecture01_002.pdf, Page 27]

### Lecture 2: Describing One-Dimensional Motion

Average velocity uses displacement, while average speed uses total distance; both are divided by elapsed time and use SI units of meters per second. [Physics 1, Physics1_Lecture02_002.pdf, Page 10]

Instantaneous velocity is the limiting rate of change of position as the time interval approaches zero. [Physics 1, Physics1_Lecture02_002.pdf, Page 15]

Acceleration is the time rate of change of velocity, with instantaneous acceleration also expressible as the second derivative of position. [Physics 1, Physics1_Lecture02_002.pdf, Page 22]

### Lecture 3: Reading Motion Graphs

The slope of the tangent to a position-time graph gives instantaneous velocity. [Physics 1, Physics1_Lecture03_002.pdf, Page 9]

The slope of a velocity-time graph gives acceleration. [Physics 1, Physics1_Lecture03_002.pdf, Page 12]

Working in reverse, the area under an acceleration-time curve changes velocity, and the area under a velocity-time curve changes position; initial conditions are needed for complete functions. [Physics 1, Physics1_Lecture03_002.pdf, Page 14]

### Lecture 4: Constant Acceleration And Free Fall

For constant acceleration, choose among three kinematic equations based on which variable is absent: one omits position, one includes initial conditions and time, and one omits time. [Physics 1, Physics1_Lecture04_002.pdf, Page 12]

Free fall means gravity is the only acceleration. Near Earth's surface the lecture uses a magnitude of 9.8 meters per second squared directed toward Earth's center and usually neglects air resistance in introductory problems. [Physics 1, Physics1_Lecture04_002.pdf, Page 19]

### Lecture 5: Vectors And Two-Dimensional Motion

A two-dimensional vector is resolved into horizontal and vertical components; converting from magnitude and direction requires trigonometry tied to the chosen axis and angle convention. [Physics 1, Physics1_Lecture05_002.pdf, Page 9]

Vector sums are found by adding corresponding components. For vectors given by magnitude and direction, first resolve components, add them, then convert back if the requested answer needs magnitude and direction. [Physics 1, Physics1_Lecture05_002.pdf, Page 15]

Two-dimensional velocity and acceleration apply the same derivative definitions component by component. [Physics 1, Physics1_Lecture05_002.pdf, Page 21] [Physics 1, Physics1_Lecture05_002.pdf, Page 22]

## Formula Sheet

### Average And Instantaneous Motion

```math
\vec{v}_{avg} = \frac{\Delta \vec{x}}{\Delta t}
s_{avg} = \frac{\mathrm{total\ distance}}{\Delta t}
\vec{v} = \frac{d\vec{x}}{dt}
```

[Physics 1, Physics1_Lecture02_002.pdf, Page 10] [Physics 1, Physics1_Lecture02_002.pdf, Page 15]

```math
\vec{a}_{avg} = \frac{\Delta \vec{v}}{\Delta t}
\vec{a} = \frac{d\vec{v}}{dt} = \frac{d^2\vec{x}}{dt^2}
```

[Physics 1, Physics1_Lecture02_002.pdf, Page 22]

### Graph Connections

```math
\vec{v}(t) = \frac{d\vec{x}}{dt}
\vec{a}(t) = \frac{d\vec{v}}{dt}
\Delta \vec{v} = \int_{t_i}^{t_f}\vec{a}(t)\,dt
\Delta \vec{x} = \int_{t_i}^{t_f}\vec{v}(t)\,dt
```

[Physics 1, Physics1_Lecture03_002.pdf, Page 9] [Physics 1, Physics1_Lecture03_002.pdf, Page 12] [Physics 1, Physics1_Lecture03_002.pdf, Page 14]

### Constant Acceleration

```math
v = v_0 + at
x - x_0 = v_0t + \frac{1}{2}at^2
v^2 - v_0^2 = 2a\Delta x
```

[Physics 1, Physics1_Lecture04_002.pdf, Page 12]

### Vector Components

```math
\vec{r} = (r_x,r_y)
r_x = r\cos\theta
r_y = r\sin\theta
\vec{A}+\vec{B} = (A_x+B_x,A_y+B_y)
```

[Physics 1, Physics1_Lecture05_002.pdf, Page 9] [Physics 1, Physics1_Lecture05_002.pdf, Page 15]

## Cross-Lecture Comparison

| Stage | Main question | Connection forward |
|---|---|---|
| Measurement | Are the units and precision consistent? | Validates every later calculation. |
| 1D kinematics | How do position, velocity, and acceleration differ? | Defines the quantities shown on motion graphs. |
| Motion graphs | What do slope and area mean physically? | Builds the derivative and integral links used by equations. |
| Constant acceleration | Which equation matches the known and unknown variables? | Provides a solvable model for free fall and other uniform acceleration. |
| 2D vectors | How is motion separated and recombined by component? | Extends the same kinematics definitions along multiple axes. |

## Common Traps

- Do not replace displacement with total distance when calculating average velocity. [Physics 1, Physics1_Lecture02_002.pdf, Page 10]
- On a position-time graph, read velocity from slope, not from vertical height. [Physics 1, Physics1_Lecture03_002.pdf, Page 9]
- On a velocity-time graph, slope gives acceleration while area gives displacement. [Physics 1, Physics1_Lecture03_002.pdf, Page 12] [Physics 1, Physics1_Lecture03_002.pdf, Page 14]
- Use the constant-acceleration equations only when acceleration is constant. [Physics 1, Physics1_Lecture04_002.pdf, Page 12]
- Choose a positive direction before assigning the sign of gravitational acceleration. Gravity points toward Earth's center. [Physics 1, Physics1_Lecture04_002.pdf, Page 19]
- Resolve vectors according to the stated angle and coordinate system before selecting sine or cosine. [Physics 1, Physics1_Lecture05_002.pdf, Page 9]

## Practice Exam

1. Explain why the two sides of a physically meaningful equation must have compatible dimensions.
2. Convert the speed of light from `3.0 x 10^8 m/s` to kilometers per second.
3. A runner travels 100 meters east and then 40 meters west in 20 seconds. Identify the displacement and total distance, then state which belongs in average velocity.
4. State what the slope of a position-time graph and the slope of a velocity-time graph represent.
5. State what the area under an acceleration-time graph and a velocity-time graph represent.
6. List the three constant-acceleration equations and identify the variable omitted by each.
7. For a vector of magnitude 24 meters at 65 degrees counterclockwise from positive x, write the component equations and estimate both components.
8. Describe the component method for adding two vectors supplied in magnitude-direction form.

## Answer Key

1. Quantities joined by addition or equality must be dimensionally compatible; inconsistent units reveal an invalid relationship. [Physics 1, Physics1_Lecture01_002.pdf, Page 27]
2. Divide by `10^3 m/km`: the result is `3.0 x 10^5 km/s`. [Physics 1, Physics1_Lecture01_002.pdf, Page 23]
3. Displacement is 60 meters east; total distance is 140 meters. Average velocity uses displacement, while average speed uses total distance. [Physics 1, Physics1_Lecture02_002.pdf, Page 10]
4. Position-time slope is velocity; velocity-time slope is acceleration. [Physics 1, Physics1_Lecture03_002.pdf, Page 9] [Physics 1, Physics1_Lecture03_002.pdf, Page 12]
5. Acceleration-time area is change in velocity; velocity-time area is change in position. [Physics 1, Physics1_Lecture03_002.pdf, Page 14]
6. `v = v_0 + at` omits position; `x - x_0 = v_0t + (1/2)at^2` includes time and initial conditions; `v^2 - v_0^2 = 2a Delta x` omits time. [Physics 1, Physics1_Lecture04_002.pdf, Page 12]
7. Use `r_x = r cos(theta)` and `r_y = r sin(theta)`. This gives approximately 10.1 meters and 21.8 meters. [Physics 1, Physics1_Lecture05_002.pdf, Page 9]
8. Resolve each vector into x and y components, add corresponding components, then convert the sum back to magnitude and direction if needed. [Physics 1, Physics1_Lecture05_002.pdf, Page 15]

## Five-Session Study Plan

1. **Units and setup:** Practice conversion factors and dimensional checks using Lecture 1 pages 23-27.
2. **Definitions:** Build a one-page contrast of distance, displacement, speed, velocity, and acceleration from Lecture 2 pages 10, 15, and 22.
3. **Graphs:** Sketch matching position, velocity, and acceleration graphs, labeling every slope and area relationship from Lecture 3 pages 9, 12, and 14.
4. **Equation selection:** For each constant-acceleration equation, hide one variable and solve a free-fall example using Lecture 4 pages 12 and 19.
5. **Components:** Resolve, add, and reconstruct vectors, then apply component-wise velocity and acceleration definitions from Lecture 5 pages 9, 15, 21, and 22.
