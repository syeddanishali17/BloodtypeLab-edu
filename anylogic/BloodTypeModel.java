import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Independent Java implementation. AnyLogic schedules step(); main() runs the same code without AnyLogic. */
public class BloodTypeModel implements AutoCloseable {
    public static final String VERSION = "1.0";
    public static final class Person {
        long id; int age, birthStep; char sex, a1, a2, r1, r2; boolean sensitized;
        String abo() { boolean a=a1=='A'||a2=='A', b=a1=='B'||a2=='B'; return a?(b?"AB":"A"):(b?"B":"O"); }
        boolean positive() { return r1=='D'||r2=='D'; }
    }
    private static final class Shock {
        String kind; int start, duration; Map<String,String> p=new LinkedHashMap<>();
        boolean active(int year) { return year>=start && year<start+duration; }
        double number(String key) { return Double.parseDouble(p.get(key)); }
        int integer(String key) { return Integer.parseInt(p.get(key)); }
    }
    private final Map<String,String> parameters=new LinkedHashMap<>();
    private final Map<String,Double> survival=new HashMap<>(), fecundity=new HashMap<>();
    private final List<Shock> shocks=new ArrayList<>();
    private final List<Person> people=new ArrayList<>();
    private final Random dynamics, immigration;
    private final PrintWriter output;
    private final double[] mortality, fertility;
    private final double[][] mutation=new double[3][3];
    private final int replicate, femaleMin, femaleMax, maleMin, maleMax, maxAge, capacity;
    private final boolean includeRh, regulation;
    private final double femaleRatio, regulationStrength, mutationRate, hdnLoss;
    public final int horizon;
    public final String bundleId;
    public final Path outputPath;
    private long nextId=0;
    public int year=0;
    public int births=0, deaths=0, arrivals=0, fetalLosses=0;

    public BloodTypeModel(Path bundle, Path outputPath, int replicate, long seed) throws IOException {
        if(replicate<0) throw new IllegalArgumentException("replicate must be non-negative");
        this.replicate=replicate; this.outputPath=outputPath;
        dynamics=new Random(seed); immigration=new Random(seed ^ 0x5DEECE66DL);
        for(Map<String,String> row:csv(bundle.resolve("parameters.csv"))) parameters.put(row.get("key"),row.get("value"));
        horizon=integer("horizon_steps"); includeRh=integer("include_rh")==1;
        femaleMin=integer("female_min_age"); femaleMax=integer("female_max_age");
        maleMin=integer("male_min_age"); maleMax=integer("male_max_age"); maxAge=integer("max_age");
        capacity=integer("carrying_capacity"); regulation=integer("regulation")==1;
        regulationStrength=number("regulation_strength"); femaleRatio=number("sex_ratio_female");
        mutationRate=number("mutation_rate"); hdnLoss=number("hdn_loss_probability");
        bundleId=parameters.get("bundle_id");
        if(bundleId==null || !bundleId.matches("[0-9a-f]{64}")) throw new IllegalArgumentException("Export a new bundle with bundle_id");
        mortality=schedule(bundle.resolve("mortality_table.csv"),"q",maxAge);
        fertility=schedule(bundle.resolve("fertility_table.csv"),"f",maxAge);
        for(Map<String,String> row:csv(bundle.resolve("selection.csv"))) {
            survival.put(row.get("phenotype"),Double.parseDouble(row.get("survival_rr")));
            fecundity.put(row.get("phenotype"),Double.parseDouble(row.get("fecundity")));
        }
        for(String type:Arrays.asList("A","B","AB","O","Rh+","Rh-"))
            if(!survival.containsKey(type)||!fecundity.containsKey(type)) throw new IllegalArgumentException("Missing selection row "+type);
        int mi=0;
        for(Map<String,String> row:csv(bundle.resolve("mutation_matrix.csv"))) {
            int from="ABO".indexOf(row.get("from"));
            if(from<0 || mi++>=3) throw new IllegalArgumentException("Invalid mutation matrix");
            for(int j=0;j<3;j++) mutation[from][j]=Double.parseDouble(row.get(String.valueOf("ABO".charAt(j))));
        }
        if(mi!=3) throw new IllegalArgumentException("Mutation matrix needs three rows");
        Map<Integer,Shock> byId=new LinkedHashMap<>();
        for(Map<String,String> row:csv(bundle.resolve("shocks.csv"))) {
            int id=Integer.parseInt(row.get("shock_id")); Shock sh=byId.get(id);
            if(sh==null){sh=new Shock();sh.kind=row.get("kind");sh.start=Integer.parseInt(row.get("start_step"));sh.duration=Integer.parseInt(row.get("duration_steps"));byId.put(id,sh);}
            sh.p.put(row.get("param"),row.get("value"));
        }
        shocks.addAll(byId.values());
        for(Map<String,String> row:csv(bundle.resolve("agents.csv"))) {
            Person p=new Person(); p.id=Long.parseLong(row.get("agent_id"));p.sex=row.get("sex").charAt(0);p.age=Integer.parseInt(row.get("age"));
            p.a1=row.get("abo_paternal").charAt(0);p.a2=row.get("abo_maternal").charAt(0);
            p.r1=row.get("rh_paternal").charAt(0);p.r2=row.get("rh_maternal").charAt(0);p.birthStep=-p.age;
            people.add(p);nextId=Math.max(nextId,p.id+1);
        }
        if(people.size()!=integer("initial_population")) throw new IllegalArgumentException("Initial population does not match parameters");
        validatePopulation();
        if(outputPath.toAbsolutePath().getParent()!=null) Files.createDirectories(outputPath.toAbsolutePath().getParent());
        output=new PrintWriter(Files.newBufferedWriter(outputPath,StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW));
        output.println("replicate,step,population,n_A,n_B,n_AB,n_O,rh_pos,bundle_id,births,deaths,immigrants,fetal_losses,engine");
        writeCounts();
    }
    private int integer(String name){return Integer.parseInt(parameters.get(name));}
    private double number(String name){return Double.parseDouble(parameters.get(name));}
    public int population(){return people.size();}
    public int count(String type){int n=0;for(Person p:people)if(p.abo().equals(type))n++;return n;}
    private double weight(Person p,Map<String,Double> weights){return weights.get(p.abo())*(includeRh?weights.get(p.positive()?"Rh+":"Rh-"):1);}
    private static double relativeRisk(double q,double rr){return 1-Math.pow(1-q,rr);}
    private static boolean contains(String set,String value){return Arrays.asList(set.split("\\|",-1)).contains(value);}
    private char drawAbo(Shock s){double u=immigration.nextDouble();return u<s.number("p_A")?'A':(u<s.number("p_A")+s.number("p_B")?'B':'O');}
    private void addImmigrants(Shock s){
        for(int i=0;i<s.integer("count_per_step");i++){
            Person p=new Person();p.id=nextId++;p.sex=immigration.nextDouble()<femaleRatio?'F':'M';
            p.age=s.integer("age_min")+immigration.nextInt(s.integer("age_max")-s.integer("age_min")+1);
            p.a1=drawAbo(s);p.a2=drawAbo(s);p.r1=includeRh&&immigration.nextDouble()<s.number("p_rh_neg_allele")?'d':'D';
            p.r2=includeRh&&immigration.nextDouble()<s.number("p_rh_neg_allele")?'d':'D';p.birthStep=year-p.age;people.add(p);arrivals++;
        }
    }
    private char transmit(char a,char b){return dynamics.nextBoolean()?a:b;}
    private char mutate(char allele){
        if(mutationRate==0 || dynamics.nextDouble()>=mutationRate)return allele;
        int i="ABO".indexOf(allele);double u=dynamics.nextDouble(),sum=0;
        for(int j=0;j<3;j++){sum+=mutation[i][j];if(u<sum)return "ABO".charAt(j);}
        return 'O';
    }
    public void step(){
        if(year>=horizon)throw new IllegalStateException("Simulation is already complete");
        int before=people.size();year++;births=deaths=arrivals=fetalLosses=0;
        for(Shock s:shocks)if(s.kind.equals("immigration")&&s.active(year))addImmigrants(s);
        for(Iterator<Person> it=people.iterator();it.hasNext();){
            Person p=it.next();double q=relativeRisk(mortality[Math.min(p.age,maxAge)],weight(p,survival));
            for(Shock s:shocks)if(s.kind.equals("disease")&&s.active(year)&&contains(s.p.get("affected_phenotypes"),p.abo())
                &&(s.p.get("affected_rh").isEmpty()||contains(s.p.get("affected_rh"),p.positive()?"Rh+":"Rh-")))
                q=s.p.get("mode").equals("relative_risk")?relativeRisk(q,s.number("relative_risk")):1-(1-q)*(1-s.number("additional_probability"));
            for(Shock s:shocks)if(s.kind.equals("bottleneck")&&s.active(year))q=1-(1-q)*(1-s.number("fraction"));
            if(dynamics.nextDouble()<q){it.remove();deaths++;}else p.age++;
        }
        List<Person> men=new ArrayList<>(),mothers=new ArrayList<>();
        double totalWeight=0;
        for(Person p:people)if(p.sex=='M'&&p.age>=maleMin&&p.age<=maleMax){men.add(p);totalWeight+=weight(p,fecundity);}
        double reg=regulation&&!people.isEmpty()?Math.pow((double)capacity/people.size(),regulationStrength):1;
        if(!men.isEmpty()&&totalWeight>0){
            for(Person p:people)if(p.sex=='F'&&p.age>=femaleMin&&p.age<=femaleMax)
                if(dynamics.nextDouble()<Math.min(1,Math.max(0,fertility[p.age]*reg*weight(p,fecundity))))mothers.add(p);
            double[] cumulative=new double[men.size()];double sum=0;
            for(int i=0;i<men.size();i++){sum+=weight(men.get(i),fecundity);cumulative[i]=sum;}
            for(Person mother:mothers){
                double pick=dynamics.nextDouble()*totalWeight;int lo=0,hi=cumulative.length-1;
                while(lo<hi){int mid=(lo+hi)>>>1;if(pick<cumulative[mid])hi=mid;else lo=mid+1;}Person father=men.get(lo);
                Person child=new Person();child.a1=mutate(transmit(father.a1,father.a2));child.a2=mutate(transmit(mother.a1,mother.a2));
                child.r1=includeRh?transmit(father.r1,father.r2):'D';child.r2=includeRh?transmit(mother.r1,mother.r2):'D';
                if(includeRh&&hdnLoss>0&&!mother.positive()&&child.positive()){
                    boolean lost=mother.sensitized&&dynamics.nextDouble()<hdnLoss;mother.sensitized=true;if(lost){fetalLosses++;continue;}
                }
                child.id=nextId++;child.sex=dynamics.nextDouble()<femaleRatio?'F':'M';child.age=0;child.birthStep=year;people.add(child);births++;
            }
        }
        if(people.size()!=before+arrivals+births-deaths)throw new IllegalStateException("Population accounting failed");
        validatePopulation();writeCounts();
    }
    private void validatePopulation(){
        Set<Long> ids=new HashSet<>();
        for(Person p:people)if(!ids.add(p.id)||p.age<0||"FM".indexOf(p.sex)<0||"ABO".indexOf(p.a1)<0||"ABO".indexOf(p.a2)<0||"Dd".indexOf(p.r1)<0||"Dd".indexOf(p.r2)<0)
            throw new IllegalStateException("Invalid or duplicate person");
    }
    private void writeCounts(){
        int a=0,b=0,ab=0,o=0,pos=0;
        for(Person p:people){switch(p.abo()){case "A":a++;break;case "B":b++;break;case "AB":ab++;break;default:o++;}if(p.positive())pos++;}
        output.println(replicate+","+year+","+people.size()+","+a+","+b+","+ab+","+o+","+pos+","+bundleId+","+births+","+deaths+","+arrivals+","+fetalLosses+",java-"+VERSION);
        output.flush();if(output.checkError())throw new IllegalStateException("Could not write "+outputPath);
    }
    @Override public void close(){output.close();}
    private static double[] schedule(Path path,String column,int maxAge)throws IOException{
        double[] result=new double[maxAge+1];boolean[] seen=new boolean[result.length];
        for(Map<String,String> row:csv(path)){int age=Integer.parseInt(row.get("age"));if(age<0||age>maxAge||seen[age])throw new IllegalArgumentException("Invalid age table");result[age]=Double.parseDouble(row.get(column));seen[age]=true;}
        for(boolean value:seen)if(!value)throw new IllegalArgumentException("Age table is incomplete");return result;
    }
    private static List<String> fields(String line){
        List<String> result=new ArrayList<>();StringBuilder b=new StringBuilder();boolean quoted=false;
        for(int i=0;i<line.length();i++){char c=line.charAt(i);if(c=='"'){if(quoted&&i+1<line.length()&&line.charAt(i+1)=='"'){b.append('"');i++;}else quoted=!quoted;}else if(c==','&&!quoted){result.add(b.toString());b.setLength(0);}else b.append(c);}
        if(quoted)throw new IllegalArgumentException("Unclosed CSV quote");result.add(b.toString());return result;
    }
    private static List<Map<String,String>> csv(Path path)throws IOException{
        List<String> lines=Files.readAllLines(path,StandardCharsets.UTF_8);if(lines.isEmpty())throw new IllegalArgumentException("Empty file "+path);
        List<String> keys=fields(lines.get(0).replace("\uFEFF",""));List<Map<String,String>> result=new ArrayList<>();
        for(int i=1;i<lines.size();i++){if(lines.get(i).trim().isEmpty())continue;List<String> cells=fields(lines.get(i));if(cells.size()!=keys.size())throw new IllegalArgumentException("Invalid CSV row "+(i+1)+" in "+path);Map<String,String> row=new LinkedHashMap<>();for(int j=0;j<keys.size();j++)row.put(keys.get(j),cells.get(j));result.add(row);}return result;
    }
    public static void main(String[] args)throws Exception{
        if(args.length<2){System.err.println("Usage: java BloodTypeModel.java BUNDLE OUTPUT_DIRECTORY [REPLICATES=20] [SEED=10001]");System.exit(2);}
        Path bundle=Paths.get(args[0]),out=Paths.get(args[1]);int reps=args.length>2?Integer.parseInt(args[2]):20;long seed=args.length>3?Long.parseLong(args[3]):10001;
        if(reps<1)throw new IllegalArgumentException("Replicates must be positive");
        for(int r=0;r<reps;r++){try(BloodTypeModel model=new BloodTypeModel(bundle,out.resolve(String.format("replicate_%04d.csv",r)),r,seed+104729L*r)){while(model.year<model.horizon)model.step();System.out.println("Completed replicate "+r+": N="+model.population());}}
    }
}
