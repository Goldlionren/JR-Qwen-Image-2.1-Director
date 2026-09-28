// ComfyUI supplies this module; it must remain external in the bundle.
// @ts-expect-error Runtime ComfyUI module
import { app } from '/scripts/app.js';
import { createApp } from 'vue';
import DirectorWidget from './components/DirectorWidget.vue';
import { deserialize } from './state';
import { detectConnectedImage, fitDetectedPerson } from './imageImport';
import './style.css';

// ComfyUI serves extension assets relative to this entry point.
const style=document.createElement('link');style.rel='stylesheet';style.href=new URL(/* @vite-ignore */ './director.css',import.meta.url).href;document.head.append(style);
const controllers=new WeakMap<object,{restore:()=>void;dispose:()=>void}>();
app.registerExtension({
  name:'JR.QwenImage21.Director',
  nodeCreated(node:any) {
    if((node.comfyClass||node.constructor?.comfyClass)!=='QwenImage21Director')return;
    (function(this:any) {
      const stateWidget=this.widgets.find((w:any)=>w.name==='director_state');
      if(!stateWidget)throw Error('Director state widget was not created');
      // Keep the actual STRING input as the serialized source of truth.
      stateWidget.type='hidden';stateWidget.computeSize=()=>[0,-4];
      stateWidget.hidden=true;
      if(stateWidget.inputEl)stateWidget.inputEl.style.display='none';
      const container=document.createElement('div');container.style.width='100%';container.style.height='100%';
      let mounted:any;
      let loading=false;
      const update=(value:string)=>{
        if(loading||stateWidget.value===value)return;
        const render=JSON.parse(value).render;
        // DOM widgets do not pass through LiteGraph's native widget callbacks.
        // Paired canvas events notify the frontend's debounced workflow tracker.
        const canvas=this.graph?app.canvas:null;
        canvas?.emitBeforeChange?.();
        try {
          stateWidget.value=value;
          for(const key of ['width','height']) {const widget=this.widgets.find((w:any)=>w.name===key);if(widget&&widget.value!==render[key])widget.value=render[key];}
          this.setDirtyCanvas?.(true,true);
        } finally {canvas?.emitAfterChange?.();}
      };
      const vue=createApp(DirectorWidget,{initial:stateWidget.value||'{}',onChange:update,
        detectImage:(progress:(s:string)=>void,signal:AbortSignal)=>detectConnectedImage(this,progress,signal),
        fitPerson:fitDetectedPerson});
      mounted=vue.mount(container);
      const dom=this.addDOMWidget('director_stage','director_stage',container,{serialize:false,hideOnZoom:false});
      dom.computeSize=()=>[700,700];dom.options.getMinHeight=()=>700;dom.options.getMaxHeight=()=>700;
      const restore=()=>{
        loading=true;
        try {
          // Older workflows serialized a null DOM-widget slot after the original eight widgets.
          // It now lands on the new combo; restore the safe default without changing old poses.
          const control=this.widgets.find((w:any)=>w.name==='controlnet_name');
          if(control&&(typeof control.value!=='string'||!control.value))control.value='disabled';
          const s=deserialize(stateWidget.value||'{}');for(const key of ['width','height'] as const){const w=this.widgets.find((w:any)=>w.name===key);if(w)s.render[key]=Number(w.value);}mounted.load(JSON.stringify(s));}
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
    }).call(node);
  },
  loadedGraphNode(node:any){controllers.get(node)?.restore();},
});
