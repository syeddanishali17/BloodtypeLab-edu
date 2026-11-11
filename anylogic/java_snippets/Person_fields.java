// =====================================================================================
// AnyLogic agent type "Person" - parameters / variables (create them in the Properties
// panel of the agent type; this file lists them with their Java types).
// =====================================================================================
//
// Parameters (set once from agents.csv or at birth):
//   int     agentId
//   char    sex            // 'F' or 'M'
//   char    aboPaternal    // 'A', 'B' or 'O'  (allele 1, from the father)
//   char    aboMaternal    // 'A', 'B' or 'O'  (allele 2, from the mother)
//   char    rhPaternal     // 'D' (Rh+) or 'd' (Rh-)
//   char    rhMaternal
//   int     birthStep
//
// Variables (change during the run):
//   int     age            // age in whole years at the start of the current year
//   boolean sensitized     // Rh- mother sensitised by an earlier Rh+ pregnancy (Rh-HDN option)
//
// Functions on Person (return type in brackets):

// [String] phenotype()
String phenotype() {
    boolean hasA = aboPaternal == 'A' || aboMaternal == 'A';
    boolean hasB = aboPaternal == 'B' || aboMaternal == 'B';
    if (hasA && hasB) return "AB";
    if (hasA) return "A";
    if (hasB) return "B";
    return "O";
}

// [boolean] isRhPositive()
boolean isRhPositive() {
    return rhPaternal == 'D' || rhMaternal == 'D';
}

// [char] transmitAbo()  - Mendel: pass one of the two alleles with probability 1/2 each
char transmitAbo() {
    return randomTrue(0.5) ? aboPaternal : aboMaternal;
}

// [char] transmitRh()
char transmitRh() {
    return randomTrue(0.5) ? rhPaternal : rhMaternal;
}
