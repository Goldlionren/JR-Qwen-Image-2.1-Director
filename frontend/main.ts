// ComfyUI supplies this module; it must remain external in the bundle.
// @ts-expect-error Runtime ComfyUI module
import { app } from '/scripts/app.js';
import { createApp } from 'vue';
import DirectorWidget from './components/DirectorWidget.vue';
import { defaults, deserialize } from './state';
import './style.css';

// ComfyUI serves extension assets relative to this entry point.
const style=document.createElement('link');style.rel='stylesheet';style.href=new URL('./director.css',import.meta.url).href;document.head.append(style);
const controllers=new WeakMap<object,{restore:()=>void;dispose:()=>void}>();
app.registerExtension({
  name:'QwenImage21.Director',
  beforeRegisterNodeDef(nodeType:any,nodeData:any) {
    if(nodeData.name!=='QwenImage21Director')return;
    const created=nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated=function(...args:any[]) {
      const result=created?.apply(this,args);
      const stateWidget=this.widgets.find((w:any)=>w.name==='director_state');
      if(!stateWidget)return result;
      // Keep the actual STRING input as the serialized source of truth.
      stateWidget.type='hidden';stateWidget.computeSize=()=>[0,-4];
      if(stateWidget.inputEl)stateWidget.inputEl.style.display='none';
      const container=document.createElement('div');container.style.width='100%';
      let mounted:any;
      let loading=false;
      const update=(value:string)=>{if(loading)return;stateWidget.value=value;this.setDirtyCanvas?.(true,true);};
      const vue=createApp(DirectorWidget,{initial:stateWidget.value||'{}',onChange:update});
      mounted=vue.mount(container);
      const dom=this.addDOMWidget('director_stage','director_stage',container,{serialize:false,hideOnZoom:false});
      dom.computeSize=()=>[700,700];dom.options.getMinHeight=()=>700;dom.options.getMaxHeight=()=>700;
      const restore=()=>{
        loading=true;
        try {const s=deserialize(stateWidget.value||'{}');for(const key of ['width','height'] as const){const w=this.widgets.find((w:any)=>w.name===key);if(w)s.render[key]=Number(w.value);}mounted.load(JSON.stringify(s));}
        catch {mounted.load(stateWidget.value);}
        finally {loading=false;}
      };
      stateWidget.serializeValue=()=>stateWidget.value;
      for(const key of ['width','height']) {
        const widget=this.widgets.find((w:any)=>w.name===key),original=widget?.callback;
        if(widget)widget.callback=function(...args:any[]){original?.apply(this,args);restore();update(mounted.getState());};
      }
      const oldConfigure=this.onConfigure;
      this.onConfigure=function(...args:any[]){const ret=oldConfigure?.apply(this,args);restore();return ret;};
      const oldRemoved=this.onRemoved;
      this.onRemoved=function(...args:any[]){vue.unmount();controllers.delete(this);return oldRemoved?.apply(this,args);};
      controllers.set(this,{restore,dispose:()=>vue.unmount()});
      this.setSize([Math.max(this.size[0],750),Math.max(this.size[1],1040)]);
      return result;
    };
  },
  loadedGraphNode(node:any){controllers.get(node)?.restore();},
});
