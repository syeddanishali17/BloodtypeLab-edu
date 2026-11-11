// =====================================================================================
// Main - "On startup" action. Loads the BloodTypeLab bundle with plain Java I/O so it works
// in every AnyLogic edition (no database import needed). Put the bundle folder next to the
// .alp model file, or change BUNDLE.
//
// Main needs:
//   population  people  (agent type Person, initially empty)
//   variables   double[] qByAge, fByAge; int femaleMin, femaleMax, maleMin, maleMax, maxAge,
//               carryingCapacity, horizon, step; double regulationStrength, sexRatioFemale,
//               hdnLoss; boolean regulation, includeRh
//   collection  java.util.Map<String,Double> survivalRR, fecundity   (keys "A","B","AB","O","Rh+","Rh-")
//   variable    java.io.PrintWriter out
// =====================================================================================

String BUNDLE = "bloodtypelab_anylogic_bundle/";

try {
    // ---------- parameters.csv  (key,value,unit,status)
    java.util.Map<String, String> p = new java.util.HashMap<>();
    java.util.List<String> lines = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(BUNDLE + "parameters.csv"));
    for (String line : lines.subList(1, lines.size())) {
        String[] c = line.split(",");
        p.put(c[0], c[1]);
    }
    horizon            = Integer.parseInt(p.get("horizon_steps"));
    femaleMin          = Integer.parseInt(p.get("female_min_age"));
    femaleMax          = Integer.parseInt(p.get("female_max_age"));
    maleMin            = Integer.parseInt(p.get("male_min_age"));
    maleMax            = Integer.parseInt(p.get("male_max_age"));
    maxAge             = Integer.parseInt(p.get("max_age"));
    sexRatioFemale     = Double.parseDouble(p.get("sex_ratio_female"));
    regulation         = Integer.parseInt(p.get("regulation")) == 1;
    carryingCapacity   = Integer.parseInt(p.get("carrying_capacity"));
    regulationStrength = Double.parseDouble(p.get("regulation_strength"));
    hdnLoss            = Double.parseDouble(p.get("hdn_loss_probability"));
    includeRh          = Integer.parseInt(p.get("include_rh")) == 1;

    // ---------- mortality_table.csv (age,q)  and fertility_table.csv (age,f)
    java.util.List<String> m = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(BUNDLE + "mortality_table.csv"));
    qByAge = new double[m.size() - 1];
    for (int i = 1; i < m.size(); i++) qByAge[i - 1] = Double.parseDouble(m.get(i).split(",")[1]);
    java.util.List<String> f = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(BUNDLE + "fertility_table.csv"));
    fByAge = new double[f.size() - 1];
    for (int i = 1; i < f.size(); i++) fByAge[i - 1] = Double.parseDouble(f.get(i).split(",")[1]);

    // ---------- selection.csv (phenotype,survival_rr,fecundity)
    java.util.List<String> s = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(BUNDLE + "selection.csv"));
    for (String line : s.subList(1, s.size())) {
        String[] c = line.split(",");
        survivalRR.put(c[0], Double.parseDouble(c[1]));
        fecundity.put(c[0], Double.parseDouble(c[2]));
    }

    // ---------- agents.csv (agent_id,sex,age,abo_paternal,abo_maternal,rh_paternal,rh_maternal)
    java.util.List<String> a = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(BUNDLE + "agents.csv"));
    for (String line : a.subList(1, a.size())) {
        String[] c = line.split(",");
        Person x = add_people();
        x.agentId     = Integer.parseInt(c[0]);
        x.sex         = c[1].charAt(0);
        x.age         = Integer.parseInt(c[2]);
        x.aboPaternal = c[3].charAt(0);
        x.aboMaternal = c[4].charAt(0);
        x.rhPaternal  = c[5].charAt(0);
        x.rhMaternal  = c[6].charAt(0);
        x.birthStep   = -x.age;
    }

    // ---------- output file (one row per year)
    out = new java.io.PrintWriter(new java.io.FileWriter("anylogic_output.csv"));
    out.println("replicate,step,population,n_A,n_B,n_AB,n_O,rh_pos");
    step = 0;
    writeCounts();   // year 0
} catch (Exception e) {
    error("Could not load BloodTypeLab bundle: " + e);
}
