import type { DesmosStrategy } from "./types";

/**
 * Hand-curated, manually verified SAT Math -> Desmos strategy knowledge base.
 *
 * This is the v1 "retrieval corpus": a flat array of strategies, each tagged
 * with a problemType and keywords so `lib/retrieval.ts` can do lightweight
 * lexical scoring against a student's problem text. Swap this module for a
 * database + embeddings lookup later without touching the API route - the
 * route only depends on `getStrategiesForProblem()`.
 */
export const knowledgeBase: DesmosStrategy[] = [
  {
    id: "linear-eq-intersection",
    problemType: "linear_equations",
    title: "Solve a linear equation via intersection",
    whenToUse:
      "Student must solve a one-variable linear equation like ax + b = cx + d, or find the x that makes an equation true.",
    desmosSyntax: [
      "y_1=3x+5",
      "y_2=20",
    ],
    steps: [
      "Type the left side of the equation as y_1 = ... on line 1.",
      "Type the right side as y_2 = ... on line 2.",
      "Click the intersection point Desmos draws where the two lines cross.",
      "The x-coordinate of that point is the solution to the equation.",
    ],
    limitations: [
      "Only works cleanly when both sides can be written as single-variable expressions in x.",
      "If the lines are parallel (no solution) or identical (infinite solutions), no single intersection point will appear - watch for that case.",
    ],
    example: {
      problem: "Solve for x: 3x + 5 = 20.",
      desmosInputs: ["y_1=3x+5", "y_2=20"],
      answer: "x = 5",
      explanation:
        "Graphing y_1=3x+5 and y_2=20 and clicking the intersection point gives (5, 20), so x = 5.",
    },
    keywords: [
      "solve for x",
      "linear equation",
      "one variable",
      "isolate",
      "value of x",
    ],
  },
  {
    id: "linear-eq-zero",
    problemType: "linear_equations",
    title: "Find a root by graphing the difference of both sides",
    whenToUse:
      "Alternative to the intersection method - useful when the equation is easier to rearrange into 'expression = 0' form.",
    desmosSyntax: ["y_1=3x+5-20"],
    steps: [
      "Move everything to one side so the equation equals 0.",
      "Type that full expression as y_1 = ... .",
      "Click the x-intercept (the point where the graph crosses the x-axis).",
      "The x-value of that point is the solution.",
    ],
    limitations: [
      "Requires correctly moving all terms to one side without an arithmetic slip.",
    ],
    example: {
      problem: "Solve for x: 3x + 5 = 20.",
      desmosInputs: ["y_1=3x+5-20"],
      answer: "x = 5",
      explanation:
        "The x-intercept of y_1 = 3x + 5 - 20 is (5, 0), so x = 5.",
    },
    keywords: ["solve for x", "linear equation", "root", "x-intercept"],
  },
  {
    id: "systems-intersection",
    problemType: "systems",
    title: "Solve a system of two equations by graphing both",
    whenToUse:
      "Student is given two equations (linear or otherwise) and asked for the (x, y) pair, sum x+y, or one coordinate that satisfies both.",
    desmosSyntax: ["y_1=2x+1", "y_2=-x+7"],
    steps: [
      "Type the first equation on line 1, solved for y if needed (or leave in ax+by=c form - Desmos can graph that directly too).",
      "Type the second equation on line 2.",
      "Click the intersection point.",
      "Read off x and y directly from the point's label, or combine them as the question asks (e.g., x + y).",
    ],
    limitations: [
      "If the system has no solution or infinitely many, Desmos will show no intersection or overlapping lines - recognize that as the answer itself.",
      "For a system with more than one intersection point (e.g., line and parabola), click through each point shown.",
    ],
    example: {
      problem: "If 2x + y = 1 and x + y = 7, what is the value of x - y?",
      desmosInputs: ["y_1=1-2x", "y_2=7-x"],
      answer: "x = -6, y = 13, so x - y = -19",
      explanation:
        "Graphing both lines (solved for y) gives intersection (-6, 13). Then x - y = -6 - 13 = -19.",
    },
    keywords: [
      "system of equations",
      "system of two equations",
      "both equations",
      "simultaneously",
    ],
  },
  {
    id: "quadratic-roots",
    problemType: "quadratics",
    title: "Find roots/zeros of a quadratic by graphing",
    whenToUse:
      "Student needs the x-intercepts (roots, zeros, solutions) of a quadratic equation set to 0.",
    desmosSyntax: ["y_1=x^2-5x+6"],
    steps: [
      "Type the quadratic expression as y_1 = ... (set equal to y, not 0).",
      "Click each x-intercept Desmos highlights - it will show the exact (x, 0) coordinates if they're rational, or a decimal approximation otherwise.",
      "If the question asks for the sum or product of roots, add or multiply the two x-values directly instead of using -b/a or c/a formulas.",
    ],
    limitations: [
      "Irrational roots display as decimals; round according to what the question wants, or use the decimal to match an answer choice.",
      "A quadratic with no real roots (negative discriminant) will show no x-intercepts.",
    ],
    example: {
      problem: "What are the solutions to x^2 - 5x + 6 = 0?",
      desmosInputs: ["y_1=x^2-5x+6"],
      answer: "x = 2 and x = 3",
      explanation:
        "The graph of y_1 = x^2 - 5x + 6 crosses the x-axis at (2, 0) and (3, 0).",
    },
    keywords: [
      "quadratic",
      "roots",
      "zeros",
      "solutions",
      "factor",
      "parabola equals zero",
    ],
  },
  {
    id: "quadratic-vertex",
    problemType: "quadratics",
    title: "Find the vertex of a parabola",
    whenToUse:
      "Question asks for the maximum/minimum value of a quadratic, or the vertex coordinates.",
    desmosSyntax: ["y_1=-2x^2+8x+3"],
    steps: [
      "Type the quadratic as y_1 = ... .",
      "Click directly on the highest (or lowest) point of the parabola - Desmos snaps to and labels the exact vertex.",
      "The y-coordinate of that point is the max/min value; the x-coordinate is where it occurs.",
    ],
    limitations: [
      "Make sure the graph window shows the vertex; drag/scroll or zoom out if it's off-screen.",
    ],
    example: {
      problem: "What is the maximum value of f(x) = -2x^2 + 8x + 3?",
      desmosInputs: ["y_1=-2x^2+8x+3"],
      answer: "11",
      explanation:
        "Clicking the peak of the parabola shows the vertex at (2, 11), so the maximum value is 11.",
    },
    keywords: [
      "maximum",
      "minimum",
      "vertex",
      "parabola",
      "max value",
      "min value",
    ],
  },
  {
    id: "function-evaluation",
    problemType: "functions",
    title: "Evaluate a function at a point",
    whenToUse:
      "Student needs f(a) for some given function f and value a, or needs to compare several function values.",
    desmosSyntax: ["f(x)=2x^2-3x+1", "f(4)"],
    steps: [
      "Define the function exactly as given: f(x) = ... on line 1.",
      "On line 2, just type f(4) (or whatever input value) - Desmos evaluates it immediately and shows the numeric result.",
      "For composite functions like f(g(2)), define both f(x) and g(x) first, then type f(g(2)).",
    ],
    limitations: [
      "Function name and variable must match exactly what was defined (case-sensitive).",
    ],
    example: {
      problem: "If f(x) = 2x^2 - 3x + 1, what is f(4)?",
      desmosInputs: ["f(x)=2x^2-3x+1", "f(4)"],
      answer: "21",
      explanation: "Typing f(4) after defining f(x) instantly evaluates to 21.",
    },
    keywords: [
      "evaluate",
      "f(x)",
      "function value",
      "composite function",
      "plug in",
    ],
  },
  {
    id: "regression-linear-quadratic",
    problemType: "regressions",
    title: "Fit a regression model to a data table",
    whenToUse:
      "Student is given a data table (x, y pairs) and asked for a line/curve of best fit, or a predicted value from that model.",
    desmosSyntax: [
      "table with columns x_1, y_1",
      "y_1~mx_1+b",
    ],
    steps: [
      "Open a table (click the '+' menu and choose table) and enter the given x and y data points into the x_1 and y_1 columns.",
      "On a new line, type the regression form matching the requested model, e.g. y_1~mx_1+b for linear or y_1~ax_1^2+bx_1+c for quadratic.",
      "Desmos fits the model and reports the parameter values (m, b, or a, b, c) - use those in the requested equation or to predict a new value.",
    ],
    limitations: [
      "Use ~ (tilde), not =, for regression - '=' will try to graph a literal equation instead of fitting one.",
      "Match the model type (linear/quadratic/exponential) to what the question implies from the data pattern or explicitly states.",
    ],
    example: {
      problem:
        "The table shows (1,3), (2,5), (3,7), (4,9). Which equation best models the data?",
      desmosInputs: ["x_1: 1,2,3,4  y_1: 3,5,7,9", "y_1~mx_1+b"],
      answer: "y = 2x + 1",
      explanation:
        "The linear regression y_1~mx_1+b returns m=2, b=1, matching y = 2x + 1 exactly.",
    },
    keywords: [
      "line of best fit",
      "regression",
      "table of values",
      "data",
      "model",
      "predict",
    ],
  },
  {
    id: "statistics-list-functions",
    problemType: "statistics",
    title: "Compute mean, median, or standard deviation of a data set",
    whenToUse:
      "Question gives a list of numbers and asks for mean, median, standard deviation, or a similar summary statistic.",
    desmosSyntax: [
      "mean(2,4,4,4,5,5,7,9)",
      "median(2,4,4,4,5,5,7,9)",
      "stdev(2,4,4,4,5,5,7,9)",
    ],
    steps: [
      "Type the statistic function you need with the data values inside parentheses, comma-separated.",
      "Desmos immediately returns the numeric result on the right side of the line.",
      "For grouped/frequency data, list each value repeated by its frequency, or use a list variable l_1=[...] first and pass l_1 into the function.",
    ],
    limitations: [
      "Very large data sets are easiest to enter as a list first (l_1=[...]) rather than typing every value into the function call.",
    ],
    example: {
      problem:
        "A data set is 2, 4, 4, 4, 5, 5, 7, 9. What is the standard deviation?",
      desmosInputs: ["stdev(2,4,4,4,5,5,7,9)"],
      answer: "≈ 2.0",
      explanation: "stdev(2,4,4,4,5,5,7,9) evaluates directly to about 2.0.",
    },
    keywords: [
      "mean",
      "median",
      "average",
      "standard deviation",
      "data set",
      "statistics",
    ],
  },
  {
    id: "circle-graph",
    problemType: "circles",
    title: "Graph a circle to read its center and radius",
    whenToUse:
      "Student is given a circle equation and asked for center, radius, a point on the circle, or whether a point lies inside/outside it.",
    desmosSyntax: ["(x-3)^2+(y+2)^2=25"],
    steps: [
      "Type the circle equation exactly as given (standard or expanded form both graph correctly).",
      "Click the center point Desmos can label, or trace the circle to read coordinates of specific points.",
      "For radius, click on any point on the circle and compare its distance to the center, or recall r is the sqrt of the constant once in standard form.",
    ],
    limitations: [
      "If given in expanded/general form, Desmos still graphs it correctly, but reading center/radius visually is easier after completing the square - consider typing both the general form and its standard-form equivalent to check.",
    ],
    example: {
      problem: "What is the radius of the circle (x - 3)^2 + (y + 2)^2 = 25?",
      desmosInputs: ["(x-3)^2+(y+2)^2=25"],
      answer: "5",
      explanation:
        "Graphing the circle and measuring from the labeled center (3, -2) to the edge confirms radius 5 (also sqrt(25)).",
    },
    keywords: ["circle", "center", "radius", "standard form"],
  },
  {
    id: "exponential-intersection",
    problemType: "exponentials",
    title: "Solve exponential growth/decay equations via intersection",
    whenToUse:
      "Student needs to solve for a variable in an exponential equation, e.g., find t when a population/value hits a target.",
    desmosSyntax: ["y_1=500*(1.03)^x", "y_2=800"],
    steps: [
      "Type the exponential model as y_1 = ... .",
      "Type the target value as y_2 = ... (a horizontal line).",
      "Click the intersection point; its x-coordinate is the answer.",
    ],
    limitations: [
      "Round according to context (e.g., 'number of years' may need rounding up to the next whole number).",
    ],
    example: {
      problem:
        "A population is modeled by P = 500(1.03)^t. After how many years does the population first exceed 800?",
      desmosInputs: ["y_1=500*(1.03)^x", "y_2=800"],
      answer: "≈ 16 years",
      explanation:
        "The intersection of the two graphs occurs near x ≈ 15.9, so the population first exceeds 800 during year 16.",
    },
    keywords: [
      "exponential",
      "growth",
      "decay",
      "compound",
      "population",
      "doubles",
    ],
  },
  {
    id: "roots-radical-intersection",
    problemType: "roots",
    title: "Solve radical (square/cube root) equations via intersection",
    whenToUse:
      "Equation contains a square root, cube root, or rational exponent and the student must solve for the variable.",
    desmosSyntax: ["y_1=\\sqrt{2x+3}", "y_2=5"],
    steps: [
      "Type the radical expression as y_1 = ... using the sqrt template (type 'sqrt' and Desmos auto-formats it).",
      "Type the target value as y_2 = ... .",
      "Click the intersection point; its x-coordinate solves the equation.",
      "Always check that the resulting x keeps the expression under the root non-negative (Desmos simply won't graph invalid regions, which itself flags extraneous solutions).",
    ],
    limitations: [
      "Desmos won't plot the radical where it's undefined, which conveniently rules out extraneous roots automatically - but still sanity check by comparing against answer choices.",
    ],
    example: {
      problem: "Solve for x: sqrt(2x + 3) = 5.",
      desmosInputs: ["y_1=\\sqrt{2x+3}", "y_2=5"],
      answer: "x = 11",
      explanation:
        "The intersection point is (11, 5), so x = 11. Squaring both sides algebraically confirms 2(11)+3 = 25 = 5^2.",
    },
    keywords: ["square root", "cube root", "radical", "sqrt"],
  },
  {
    id: "intersections-nonlinear",
    problemType: "intersections",
    title: "Find all intersection points of two different curve types",
    whenToUse:
      "Question describes two different kinds of graphs (e.g., a line and a parabola, or two curves) and asks how many times or where they meet.",
    desmosSyntax: ["y_1=x^2-1", "y_2=x+1"],
    steps: [
      "Graph each relation on its own line exactly as given.",
      "Click every point Desmos highlights where the graphs cross - it labels each one.",
      "Count the labeled points to answer 'how many solutions/intersections' questions, or read coordinates directly for 'at what point' questions.",
    ],
    limitations: [
      "Make sure the visible window is wide enough to catch all intersection points - zoom out if the question suggests values outside the default view.",
    ],
    example: {
      problem: "How many points of intersection do y = x^2 - 1 and y = x + 1 have?",
      desmosInputs: ["y_1=x^2-1", "y_2=x+1"],
      answer: "2",
      explanation:
        "Desmos labels two intersection points: (-1, 0) and (2, 3).",
    },
    keywords: [
      "intersect",
      "intersection",
      "how many solutions",
      "meet",
      "points in common",
    ],
  },
  {
    id: "tables-plug-and-check",
    problemType: "tables",
    title: "Use a Desmos table to plug in and check multiple values fast",
    whenToUse:
      "Question gives an expression/equation and several candidate x-values (often multiple choice) and asks which one satisfies a condition.",
    desmosSyntax: [
      "table with x_1 = candidate values",
      "y_1=2x_1^2-3x_1-1 (or the condition to test)",
    ],
    steps: [
      "Open a table and enter every candidate value (e.g., the four answer choices) into the x_1 column.",
      "In the y_1 column header, type the expression or condition from the problem using x_1.",
      "Desmos fills in the corresponding output for every row at once - scan for the row that matches what the question asks (e.g., y_1 = 0, or the largest y_1).",
    ],
    limitations: [
      "Best suited to 'which value works' or 'plug in the answer choices' style questions rather than open-ended solves.",
    ],
    example: {
      problem:
        "Which value of x satisfies 2x^2 - 3x - 1 = 4? (A) -1 (B) 1 (C) 2.5 (D) -0.5",
      desmosInputs: ["x_1: -1,1,2.5,-0.5", "y_1=2x_1^2-3x_1-1"],
      answer: "x = 2.5",
      explanation:
        "The table shows y_1 = 4 only in the row where x_1 = 2.5, so that's the answer choice that works.",
    },
    keywords: [
      "table",
      "which value",
      "plug in",
      "answer choices",
      "satisfies",
    ],
  },
  {
    id: "maxima-minima-click-point",
    problemType: "maxima_minima",
    title: "Read a maximum or minimum directly off any graph",
    whenToUse:
      "Question asks for the max/min of any function (not just a quadratic) over all reals or over a restricted interval.",
    desmosSyntax: ["y_1=-x^3+3x^2+2", "y_1\\{0\\le x\\le 3\\}"],
    steps: [
      "Graph the function as y_1 = ... .",
      "If the question restricts the domain, add the restriction in curly braces, e.g. y_1{0<=x<=3}, so Desmos only draws (and lets you click points on) that piece.",
      "Click the peak or valley Desmos highlights - it snaps to and labels the exact max/min point.",
    ],
    limitations: [
      "For functions without a clean closed form max/min, Desmos gives a decimal approximation - match it to the closest answer choice.",
    ],
    example: {
      problem:
        "What is the maximum value of f(x) = -x^3 + 3x^2 + 2 on the interval 0 ≤ x ≤ 3?",
      desmosInputs: ["y_1=-x^3+3x^2+2", "y_1\\{0\\le x\\le 3\\}"],
      answer: "6",
      explanation:
        "Restricting the graph to [0, 3] and clicking the peak shows the point (2, 6), the maximum on that interval.",
    },
    keywords: [
      "maximum",
      "minimum",
      "max",
      "min",
      "over the interval",
      "highest point",
      "lowest point",
    ],
  },
  {
    id: "slider-parameter-exploration",
    problemType: "functions",
    title: "Use a slider to explore how a parameter changes a graph",
    whenToUse:
      "Question describes a family of functions/equations with an unknown constant (like a, k, or h) and asks how changing it affects the graph, or what value produces a given behavior.",
    desmosSyntax: ["y_1=a(x-2)^2+3", "a=1"],
    steps: [
      "Type the equation with the unknown letter (e.g., a) instead of a number.",
      "Click the letter or the '+' prompt Desmos gives to add it as a slider.",
      "Drag the slider and watch the graph update live until it matches the condition described (passes through a given point, has a given number of roots, etc.).",
      "Read the slider's current value as your answer.",
    ],
    limitations: [
      "Best for 'for what value of k does...' conceptual questions; for a precise numeric answer, narrow the slider's step size for finer control.",
    ],
    example: {
      problem:
        "For what value of a does the graph of y = a(x - 2)^2 + 3 pass through (4, 11)?",
      desmosInputs: ["y_1=a(x-2)^2+3", "a=1"],
      answer: "a = 2",
      explanation:
        "Dragging the slider for a until the curve passes through (4, 11) lands at a = 2; plugging in confirms 2(2)^2+3 = 11.",
    },
    keywords: ["slider", "parameter", "family of functions", "constant", "for what value"],
  },
];
