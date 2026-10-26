// Native regression of production input parsing/GCPad conversion. No OS input or output.
#include "Common/IniFile.h"
#include "moderngekko/runtime.hpp"
#include "Core/HW/GCPad.h"
#include "InputCommon/ControllerEmu/ControlGroup/ControlGroup.h"
#include <filesystem>
#include "Core/HW/GCPadEmu.h"
#include "InputCommon/ControlReference/ControlReference.h"
#include "InputCommon/ControllerInterface/ControllerInterface.h"
#include "InputCommon/ControllerInterface/CoreDevice.h"
#include "InputCommon/GCPadStatus.h"
#include <cstdio>
#include <map>
#include <memory>
#include <string>
#include <vector>

class FakeDevice final : public ciface::Core::Device {
public:
  std::string source,name;
  std::map<std::string,double> values;
  struct Input final : ciface::Core::Device::Input {
    std::string name; double& value;
    Input(std::string n,double& v):name(std::move(n)),value(v){}
    std::string GetName() const override{return name;}
    ControlState GetState() const override{return value;}
  };
  FakeDevice(std::string s,std::string n,int id,const std::vector<std::string>& inputs):source(std::move(s)),name(std::move(n)){
    SetId(id);for(const auto& input:inputs)AddInput(new Input(input,values[input]));
  }
  std::string GetName() const override{return name;}
  std::string GetSource() const override{return source;}
  void Clear(){for(auto& [key,value]:values)value=0;}
};
class FixtureInterface final : public ControllerInterface {
public:
  void Add(std::shared_ptr<FakeDevice> device){m_devices.push_back(std::move(device));}
  void RemovePads(){std::erase_if(m_devices,[](const auto& d){return d->GetSource()=="XInput";});}
};
int main(int argc,char** argv){
 if(argc==4 && std::string(argv[1])=="--inspect-runtime"){
   const std::filesystem::path root=argv[2];
   moderngekko::RuntimeConfig config;config.game_root=root/"original/GWWE01";config.user_directory=argv[3];
   config.module=moderngekko::ModuleSource::DynamicPath(root/"build/module-full-vectors/Release/gGWWE01_recomp.dll");
   config.headless=true;config.graphics.backend="OpenGL";config.audio.mute=true;
   auto created=moderngekko::Runtime::Create(std::move(config));
   if(!created){std::printf("runtime create failed: %s\n",created.error->message.c_str());return 4;}
   for(const auto& name:g_controller_interface.GetAllDeviceStrings())std::printf("device=%s\n",name.c_str());
   auto* buttons=Pad::GetGroup(0,PadGroup::Buttons);
   int missing=0;
   for(const auto& control:buttons->controls){
     std::printf("button=%s bound=%d expression=%s\n",control->name.c_str(),control->control_ref->BoundCount(),control->control_ref->GetExpression().c_str());
     if(control->control_ref->BoundCount()==0)++missing;
   }
   std::printf("connected=%d missing_button_bindings=%d\n",Pad::GetStatus(0).isConnected,missing);
   return missing?1:0;
 }
 if(argc!=2)return 2;
 Common::IniFile ini;if(!ini.Load(argv[1]))return 3;
 FixtureInterface ci;
 auto keyboard=std::make_shared<FakeDevice>("DInput","Keyboard Mouse",0,std::vector<std::string>{"X","Z","C","S","D","RETURN","UP","DOWN","LEFT","RIGHT","I","K","J","L","T","G","F","H","Q","W"});
 ci.Add(keyboard);
 std::vector<std::shared_ptr<FakeDevice>> pads;
 for(int i=0;i<4;i++){auto d=std::make_shared<FakeDevice>("XInput","Gamepad",i,std::vector<std::string>{"Button A","Button B","Button X","Button Y","Shoulder L","Shoulder R","Start","Pad N","Pad S","Pad W","Pad E","Left X+","Left X-","Left Y+","Left Y-","Right X+","Right X-","Right Y+","Right Y-","Trigger L","Trigger R"});pads.push_back(d);ci.Add(d);}
 GCPad gc(0);gc.LoadConfig(ini.GetOrCreateSection("GCPad1"));gc.UpdateReferences(ci);ControlReference::SetInputGate(true);
 int cases=0,failed=0;
 auto check=[&](bool ok,const char* name){++cases;if(!ok){++failed;std::printf("FAIL %s\n",name);}};
 auto clear=[&](){keyboard->Clear();for(auto& d:pads)d->Clear();};
 check(gc.GetInput().isConnected,"connected");
 const std::vector<std::pair<std::string,u16>> buttons={{"Button A",PAD_BUTTON_A},{"Button B",PAD_BUTTON_B},{"Button X",PAD_BUTTON_X},{"Button Y",PAD_BUTTON_Y},{"Shoulder R",PAD_TRIGGER_Z},{"Start",PAD_BUTTON_START},{"Pad N",PAD_BUTTON_UP},{"Pad S",PAD_BUTTON_DOWN},{"Pad W",PAD_BUTTON_LEFT},{"Pad E",PAD_BUTTON_RIGHT},{"Shoulder L",PAD_TRIGGER_L}};
 for(int slot=0;slot<4;slot++)for(auto& [key,mask]:buttons){clear();pads[slot]->values[key]=1;check((gc.GetInput().button&mask)!=0,(std::to_string(slot)+" "+key).c_str());}
 for(auto& key:std::vector<std::string>{"Left X+","Left X-","Left Y+","Left Y-","Right X+","Right X-","Right Y+","Right Y-"}){
   clear();pads[0]->values[key]=1;auto state=gc.GetInput();int value=key.starts_with("Left X")?state.stickX:key.starts_with("Left Y")?state.stickY:key.starts_with("Right X")?state.substickX:state.substickY;
   check(key.back()=='+'?value>160:value<96,key.c_str());
 }
 clear();pads[0]->values["Left X+"]=.05;check(gc.GetInput().stickX==128,"deadzone");
 for(int slot=0;slot<4;slot++)for(bool left:{false,true}){
   clear();pads[slot]->values[left?"Trigger L":"Trigger R"]=.5;auto a=gc.GetInput();check((a.button&(left?PAD_TRIGGER_L:PAD_TRIGGER_R))==0,"half trigger no click");check((left?a.triggerLeft:a.triggerRight)>80,"half trigger analog");
   pads[slot]->values[left?"Trigger L":"Trigger R"]=1;check((gc.GetInput().button&(left?PAD_TRIGGER_L:PAD_TRIGGER_R))!=0,"full trigger click");
 }
 clear();keyboard->values["X"]=1;check((gc.GetInput().button&PAD_BUTTON_A)!=0,"keyboard A");
 clear();keyboard->values["RETURN"]=1;check((gc.GetInput().button&PAD_BUTTON_START)!=0,"keyboard Start");
 clear();keyboard->values["UP"]=1;check(gc.GetInput().stickY>160,"keyboard analog Up");
 ci.RemovePads();gc.UpdateReferences(ci);check(gc.GetInput().isConnected,"keyboard stays connected after unplug");check(gc.GetInput().stickY>160,"keyboard after unplug");
 clear();ci.Add(pads[3]);gc.UpdateReferences(ci);pads[3]->values["Button A"]=1;check((gc.GetInput().button&PAD_BUTTON_A)!=0,"hotplug slot3");
 clear();check(gc.GetInput().button==0,"release buttons");
 std::printf("cases=%d failed=%d\n",cases,failed);return failed?1:0;
}
