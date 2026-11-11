// =====================================================================================
// Main - cyclic Event "yearStep": Trigger = Timeout, Mode = Cyclic, first occurrence 1,
// recurrence 1 (model time unit = years). Same chronology as the Python engine:
//   1 immigration  2 mortality (one draw)  3 ageing  4 reproduction  5 count.
// Shocks: read shocks.csv on startup and apply them inside the marked blocks (omitted here
// for brevity; see docs/anylogic_integration.md).
// =====================================================================================

step++;

// ---------- 1. Immigration (if a shock is active this year) ------------------------
// for (int i = 0; i < immigrantsThisYear; i++) { Person x = add_people(); ... HWE alleles ... }

// ---------- 2. Mortality: exactly one Bernoulli draw per agent ------------------------
java.util.List<Person> dead = new java.util.ArrayList<>();
for (Person x : people) {
    double q = qByAge[Math.min(x.age, maxAge)];
    double rr = survivalRR.get(x.phenotype()) * (includeRh ? survivalRR.get(x.isRhPositive() ? "Rh+" : "Rh-") : 1.0);
    if (rr != 1.0) q = 1.0 - Math.pow(1.0 - q, rr);
    // disease / bottleneck shocks: q = 1 - (1 - q) * (1 - qExtra);
    if (uniform() < q) dead.add(x);
}
for (Person x : dead) remove_people(x);

// ---------- 3. Ageing ------------------------------------------------------------------
for (Person x : people) x.age++;

// ---------- 4. Reproduction --------------------------------------------------------------
int n = people.size();
double reg = (regulation && n > 0) ? Math.pow((double) carryingCapacity / n, regulationStrength) : 1.0;
java.util.List<Person> men = new java.util.ArrayList<>();
java.util.List<Person> mothers = new java.util.ArrayList<>();
for (Person x : people) {
    if (x.sex == 'M' && x.age >= maleMin && x.age <= maleMax) men.add(x);
}
if (!men.isEmpty()) {
    for (Person w : people) {
        if (w.sex != 'F' || w.age < femaleMin || w.age > femaleMax) continue;
        double pb = fByAge[w.age] * reg * fecundity.get(w.phenotype());
        if (uniform() < Math.min(1.0, pb)) mothers.add(w);
    }
    for (Person mother : mothers) {
        Person father = men.get(uniform_discr(0, men.size() - 1));   // uniform random eligible man
        char aboP = father.transmitAbo(), aboM = mother.transmitAbo();
        char rhP = father.transmitRh(),   rhM = mother.transmitRh();
        boolean childPos = rhP == 'D' || rhM == 'D';
        if (includeRh && hdnLoss > 0 && !mother.isRhPositive() && childPos) {
            boolean lost = mother.sensitized && uniform() < hdnLoss;
            mother.sensitized = true;
            if (lost) continue;
        }
        Person c = add_people();
        c.sex = uniform() < sexRatioFemale ? 'F' : 'M';
        c.age = 0;
        c.aboPaternal = aboP; c.aboMaternal = aboM;
        c.rhPaternal = rhP;   c.rhMaternal = rhM;
        c.birthStep = step;
    }
}

// ---------- 5. Count and write ------------------------------------------------------------
writeCounts();
if (step >= horizon) { out.close(); finishSimulation(); }

// ---------- Function writeCounts() on Main (void) ------------------------------------------
// int a = 0, b = 0, ab = 0, o = 0, pos = 0;
// for (Person x : people) {
//     switch (x.phenotype()) { case "A": a++; break; case "B": b++; break; case "AB": ab++; break; default: o++; }
//     if (x.isRhPositive()) pos++;
// }
// out.println(replicate + "," + step + "," + people.size() + "," + a + "," + b + "," + ab + "," + o + "," + pos);
// ('replicate' is an int parameter of Main: 0 in a simple experiment; in a Parameter Variation
//  experiment vary it 0..k-1 and write one file per replicate or append to a shared file)
// Note: with a non-neutral fecundity preset, choose fathers with probability proportional to
// fecundity (as the Python engine does) instead of uniformly.
