"""Generate a self-contained AnyLogic 8.9 ALP shell around the independent Java model.

The ALP schema follows the public AnyLogic-company Alpyne examples. This generator
does not compile the proprietary AnyLogic shell; open/build it in AnyLogic separately.
"""
from pathlib import Path
from xml.dom.minidom import Document

ROOT = Path(__file__).resolve().parent.parent


def build() -> Path:
    source = (ROOT / "anylogic/BloodTypeModel.java").read_text(encoding="utf-8")
    imports, body = source.split("/** Independent", 1)
    body = "/** Independent" + body
    body = body.replace("public class BloodTypeModel", "public static class BloodTypeModel", 1)
    doc = Document()
    def tag(parent, name, text=None, attrs=None, code=False):
        e = doc.createElement(name)
        for k, v in (attrs or {}).items():
            e.setAttribute(k, v)
        if text is not None:
            e.appendChild(doc.createCDATASection(str(text)) if code else doc.createTextNode(str(text)))
        parent.appendChild(e)
        return e
    workspace=tag(doc,"AnyLogicWorkspace",attrs={"WorkspaceVersion":"1.9","AnyLogicVersion":"8.9.3.202411201859","AlpVersion":"8.9.2"})
    model=tag(workspace,"Model")
    for key,value in [("Id",1811000000000),("Name","BloodTypeLab"),("Description","Independent Java agent model scheduled yearly in AnyLogic. See README_ANYLOGIC.md. Editor build verification remains required."),("EngineVersion",6),("JavaPackageName","bloodtypelab_anylogic"),("ModelTimeUnit","Year")]:tag(model,key,value)
    tag(model,"Folders")
    agents=tag(model,"ActiveObjectClasses"); main=tag(agents,"ActiveObjectClass")
    tag(main,"Id",1811000000001);tag(main,"Name","Main")
    extra='''public BloodTypeModel model;
public java.util.List<BloodTypeModel> models = new java.util.ArrayList<>();
public java.nio.file.Path outputFolder;
'''+body
    tag(main,"AdditionalClassCode",extra,code=True);tag(main,"Import",imports,code=True)
    startup='''try {
    if (replicateCount < 1) throw new IllegalArgumentException("replicateCount must be positive");
    java.nio.file.Path bundle = java.nio.file.Paths.get(bundleDirectory).toAbsolutePath();
    outputFolder = bundle.resolve("anylogic_results_" + java.util.UUID.randomUUID().toString());
    for (int r = 0; r < replicateCount; r++) {
        BloodTypeModel instance = new BloodTypeModel(bundle,
            outputFolder.resolve(String.format("replicate_%04d.csv", r)), r, dynamicsSeed + 104729L * r);
        models.add(instance);
    }
    model = models.get(0);
    statusText.setText("Loaded " + replicateCount + " replicates.\\nOutput: " + outputFolder);
    traceln("BloodTypeLab outputs: " + outputFolder);
} catch (Exception e) {
    for (BloodTypeModel instance : models) instance.close();
    throw new RuntimeException("Set bundleDirectory to the folder containing parameters.csv. " + e, e);
}'''
    tag(main,"StartupCode",startup,code=True)
    tag(main,"DestroyCode","for (BloodTypeModel instance : models) instance.close();",code=True)
    for k,v in [("Generic","false"),("FlowChartsUsage","ENTITY"),("SamplesToKeep",100),("LimitNumberOfArrayElements","false"),("ElementsLimitValue",100),("MakeDefaultViewArea","true"),("SceneSkybox","null"),("CurrentLevel",1811000000003),("ConnectionsId",1811000000004)]:tag(main,k,v)
    env=tag(main,"EnvironmentProperties")
    for k,v in [("EnableSteps","false"),("SpaceType","CONTINUOUS"),("WidthCode",1000),("HeightCode",600),("ZHeightCode",0),("ColumnsCountCode",100),("RowsCountCode",100),("NeigborhoodType","MOORE"),("LayoutType","USER_DEF"),("NetworkType","USER_DEF")]:tag(env,k,v)
    variables=tag(main,"Variables")
    params=[("bundleDirectory","String",'"."'),("replicateCount","int","20"),("dynamicsSeed","long","10001L")]
    for i,(name,typ,default) in enumerate(params):
        v=tag(variables,"Variable",attrs={"Class":"Parameter"})
        for k,val in [("Id",1811000000100+i),("Name",name),("X",40),("Y",-80+i*30),("PublicFlag","true"),("PresentationFlag","false"),("ShowLabel","true")]:tag(v,k,val)
        prop=tag(v,"Properties",attrs={"SaveInSnapshot":"true","ModificatorType":"STATIC"})
        tag(prop,"Type",typ,code=True);tag(prop,"UnitType","NONE");tag(prop,"SdArray","false")
        value=tag(prop,"DefaultValue",attrs={"Class":"CodeValue"});tag(value,"Code",default,code=True)
    events=tag(main,"Events");event=tag(events,"Event")
    for k,v in [("Id",1811000000200),("Name","yearStep"),("X",250),("Y",-60),("PublicFlag","false"),("PresentationFlag","false"),("ShowLabel","true")]:tag(event,k,v)
    prop=tag(event,"Properties",attrs={"TriggerType":"timeout","Mode":"cyclic"})
    for name in ("Timeout","OccurrenceTime","RecurrenceCode"):
        v=tag(prop,name,attrs={"Class":"CodeUnitValue"});tag(v,"Code","1",code=True);tag(v,"Unit","YEAR",attrs={"Class":"TimeUnits"},code=True)
    tag(prop,"OccurrenceAtTime","true");tag(prop,"OccurrenceDate",0);tag(prop,"Condition","false",code=True)
    action='''for (BloodTypeModel instance : models) instance.step();
statusText.setText("Year " + model.year + " / " + model.horizon + "    Replicates: " + models.size()
    + "\\nFirst replicate population: " + model.population()
    + "\\nA: " + model.count("A") + "    B: " + model.count("B") + "    AB: " + model.count("AB") + "    O: " + model.count("O")
    + "\\n\\nOutput: " + outputFolder);
if (model.year >= model.horizon) {
    for (BloodTypeModel instance : models) instance.close();
    traceln("All replicates complete. " + outputFolder);
    finishSimulation();
}'''
    tag(event,"Action",action,code=True)
    tag(main,"Functions");tag(main,"EmbeddedObjects")
    presentation=tag(main,"Presentation");level=tag(presentation,"Level")
    for k,v in [("Id",1811000000003),("Name","level"),("X",0),("Y",0),("PublicFlag","true"),("PresentationFlag","true"),("ShowLabel","false"),("DrawMode","SHAPE_DRAW_2D3D"),("Z",0),("LevelVisibility","DIM_NON_CURRENT")]:tag(level,k,v)
    shapes=tag(level,"Presentation")
    for i,(name,text,y,size) in enumerate([("titleText","BloodTypeLab",40,32),("statusText","Loading the exported bundle...",115,20),("descriptionText","Independent Java agent model. AnyLogic advances each replicate once per model year.",390,18)]):
        shape=tag(shapes,"Text")
        for k,v in [("Id",1811000000300+i),("Name",name),("X",40),("Y",y),("PublicFlag","true"),("PresentationFlag","true"),("ShowLabel","false"),("DrawMode","SHAPE_DRAW_2D3D"),("EmbeddedIcon","false"),("Z",0),("Rotation",0),("Color",-15651005),("Text",text),("Alignment","LEFT")]:tag(shape,k,v)
        font=tag(shape,"Font");tag(font,"Name","SansSerif");tag(font,"Size",size);tag(font,"Style",0)
    frame=tag(model,"Frame");tag(frame,"Width",1000);tag(frame,"Height",600)
    experiments=tag(model,"Experiments");experiment=tag(experiments,"SimulationExperiment",attrs={"ActiveObjectClassId":"1811000000001"})
    for k,v in [("Id",1811000000400),("Name","Simulation"),("MaximumMemory",1024),("RandomNumberGenerationType","fixedSeed"),("CustomGeneratorCode","new Random()"),("SeedValue",1),("SelectionModeForSimultaneousEvents","LIFO"),("LoadRootFromSnapshot","false")]:tag(experiment,k,v)
    tag(experiment,"Variables");tag(experiment,"Functions");tag(experiment,"Presentation")
    parameter_values=tag(experiment,"Parameters")
    for name,typ,default in params:
        p=tag(parameter_values,"Parameter");tag(p,"ParameterName",name,code=True);value=tag(p,"ParameterValue",attrs={"Class":"CodeValue"});tag(value,"Code",default,code=True)
    props=tag(experiment,"PresentationProperties")
    for k,v in [("EnableZoomAndPanning","true"),("ExecutionMode","fast"),("Title","BloodTypeLab : Simulation"),("EnableDeveloperPanel","true"),("ShowDeveloperPanelOnStart","true"),("RealTimeScale",1)]:tag(props,k,v)
    time=tag(experiment,"ModelTimeProperties")
    for k,v in [("StopOption","Never"),("InitialDate",0),("InitialTime",0),("FinalDate",0),("FinalTime",1000)]:tag(time,k,v)
    tag(experiment,"BypassInitialScreen","true")
    out=ROOT/"anylogic/BloodTypeLab.alp"
    out.write_bytes(doc.toprettyxml(indent="  ",encoding="UTF-8"))
    return out


if __name__=="__main__":
    print(build())
