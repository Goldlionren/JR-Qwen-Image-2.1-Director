<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { clone, defaults, deserialize, preset, rig, wrap, type DirectorState, type Mode } from '../state';
import { DirectorScene } from '../three/DirectorScene';
import { makeRig,updateRig,worldPoints } from '../three/geometry';
import NumberField from './NumberField.vue';
const props=defineProps<{initial:string;onChange:(value:string)=>void}>();
const state=reactive<DirectorState>(defaults());
const host=ref<HTMLElement>(), preview=ref<HTMLCanvasElement>(), error=ref(''),jsonOpen=ref(false),jsonText=ref('');
let stage:DirectorScene|undefined,restoring=false,timer:ReturnType<typeof setTimeout>|undefined;
const history:string[]=[],future:string[]=[];const undoCount=ref(0),redoCount=ref(0);
const selected=computed(()=>state.pose.joints[state.ui.selected_joint]);
const angles=['Front','Front Right ¾','Right','Back Right ¾','Back','Back Left ¾','Left','Front Left ¾'];
const modes:Mode[]=['CAMERA','ACTOR','POSE'];
const relative=computed(()=>wrap(state.camera.azimuth-state.actor.yaw).toFixed(1));
const hint=computed(()=>state.ui.mode==='CAMERA'?'左键转摄影机 · 滚轮推拉 · Shift 拖动目标':state.ui.mode==='ACTOR'?'左键转人物 · Shift 拖动位置':'点击关节旋转 · 拖动手腕/脚踝执行 IK');
function restore(value:string) {
  try {const next=deserialize(value);restoring=true;Object.assign(state,next);stage?.setState(state);error.value='';}
  catch(e) {error.value=String(e);} finally {restoring=false;}
}
function remember() {
  const value=JSON.stringify(state);if(history[history.length-1]!==value){history.push(value);if(history.length>60)history.shift();future.length=0;}
  undoCount.value=history.length-1;redoCount.value=future.length;
}
function flush() {clearTimeout(timer);remember();}
function commit() {
  if(restoring)return;
  props.onChange(JSON.stringify(state));stage?.update();clearTimeout(timer);timer=setTimeout(remember,220);
}
function undo() {flush();if(history.length<2)return;future.push(history.pop()!);restore(history[history.length-1]);props.onChange(JSON.stringify(state));undoCount.value=history.length-1;redoCount.value=future.length;}
function redo() {clearTimeout(timer);const value=future.pop();if(!value)return;history.push(value);restore(value);props.onChange(value);undoCount.value=history.length-1;redoCount.value=future.length;}
function load(value:string) {clearTimeout(timer);restore(value);history.splice(0,history.length,JSON.stringify(state));future.length=0;undoCount.value=redoCount.value=0;}
function posePreset(name:string) {flush();preset(state,name);commit();}
function shot(name:string) {
  const p=state.actor.position,scale=state.actor.scale;
  const [distance,y]=name==='Full Body'?[3.1,.95]:name==='Medium'?[1.8,1.3]:[.85,1.63];
  state.camera.target=[p[0],p[1]+y*scale,p[2]];state.camera.distance=distance*scale;state.camera.fov=40;
}
function eyeLevel() {
  const r=makeRig();updateRig(r,state);const head=worldPoints(r).head;
  const ratio=(head.y-state.camera.target[1])/state.camera.distance;
  state.camera.elevation=Math.asin(Math.max(-.9998,Math.min(.9998,ratio)))*180/Math.PI;
}
function importJson() {try {deserialize(jsonText.value);restore(jsonText.value);props.onChange(JSON.stringify(state));remember();jsonOpen.value=false;}catch(e){error.value=String(e);}}
function exportJson() {jsonText.value=JSON.stringify(state,null,2);jsonOpen.value=!jsonOpen.value;}
function keydown(e:KeyboardEvent) {
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)){e.preventDefault();e.shiftKey?redo():undo();}
}
watch(state,commit,{deep:true,flush:'sync'});
onMounted(()=>{
  restore(props.initial);remember();
  try {stage=new DirectorScene(host.value!,preview.value!,state,commit);}catch(e){error.value=`3D 初始化失败：${String(e)}`;}
});
onBeforeUnmount(()=>{clearTimeout(timer);stage?.dispose();});
defineExpose({load,getState:()=>JSON.stringify(state)});
</script>
<template>
 <section class="qd-director" @pointerdown.stop @wheel.stop @keydown.stop="keydown">
  <header class="qd-header"><div><span class="qd-eyebrow">JR Qwen Image 2.1 Director</span><strong>导演台 <small>Director</small></strong></div><span class="qd-badge">BODY RIG · 01</span></header>
  <nav class="qd-toolbar"><div class="qd-tabs"><button v-for="mode in modes" :key="mode" :class="{active:state.ui.mode===mode}" @click="state.ui.mode=mode">{{mode}} <small>{{mode==='CAMERA'?'摄影机':mode==='ACTOR'?'人物':'姿态'}}</small></button></div><div><button title="Undo" :disabled="undoCount<1" @click="undo">↶</button><button title="Redo" :disabled="redoCount<1" @click="redo">↷</button><button @click="exportJson">JSON</button></div></nav>
  <div class="qd-workspace">
   <aside class="qd-panel">
    <template v-if="state.ui.mode==='CAMERA'">
     <div class="qd-section-title">VIRTUAL CAMERA <span>连续机位</span></div>
     <div class="qd-presets"><button v-for="(label,i) in angles" :key="label" :class="{chosen:Math.abs(state.camera.azimuth-i*45)<.1}" @click="state.camera.azimuth=i*45">{{label}}</button></div>
     <NumberField label="Azimuth" v-model="state.camera.azimuth" :min="0" :max="359.9" :step=".1" unit="°"/>
     <NumberField label="Elevation" v-model="state.camera.elevation" :min="-89" :max="89" :step=".1" unit="°"/>
     <NumberField label="Distance" v-model="state.camera.distance" :min=".2" :max="15" :step=".01"/>
     <NumberField label="FOV" v-model="state.camera.fov" :min="10" :max="120" :step=".1" unit="°"/>
     <NumberField label="Camera roll" v-model="state.camera.roll" :min="-180" :max="180" :step=".1" unit="°"/>
     <div class="qd-presets"><button @click="state.camera.elevation=-20">Low</button><button @click="eyeLevel">Eye Level</button><button @click="state.camera.elevation=20">Elevated</button><button @click="state.camera.elevation=55">High</button></div>
     <div class="qd-presets"><button v-for="p in ['Full Body','Medium','Close']" @click="shot(p)">{{p}}</button></div>
     <details><summary>Target / 注视点</summary><NumberField v-for="(axis,i) in ['X','Y','Z']" :label="`Target ${axis}`" v-model="state.camera.target[i]" :min="-10" :max="10" :step=".01"/></details>
    </template>
    <template v-else-if="state.ui.mode==='ACTOR'">
     <div class="qd-section-title">ACTOR ROOT <span>整体变换</span></div>
     <NumberField label="Actor yaw" v-model="state.actor.yaw" :min="-180" :max="360" :step=".1" unit="°"/>
     <NumberField label="Actor pitch" v-model="state.actor.pitch" :min="-180" :max="180" :step=".1" unit="°"/>
     <NumberField label="Actor roll" v-model="state.actor.roll" :min="-180" :max="180" :step=".1" unit="°"/>
     <NumberField label="Actor scale" v-model="state.actor.scale" :min=".1" :max="5" :step=".01"/>
     <NumberField v-for="(axis,i) in ['X','Y','Z']" :label="`Position ${axis}`" v-model="state.actor.position[i]" :min="-10" :max="10" :step=".01"/>
     <button class="qd-wide" @click="state.actor=defaults().actor">Reset actor</button>
    </template>
    <template v-else>
     <div class="qd-section-title">POSE RIG <span>固定骨长</span></div>
     <label class="qd-select">Preset<select aria-label="Pose preset" :value="state.pose.preset" @change="posePreset(($event.target as HTMLSelectElement).value)"><option v-if="state.pose.preset==='Custom'">Custom</option><option v-for="(_,name) in rig.presets">{{name}}</option></select></label>
     <label class="qd-select">Joint<select aria-label="Selected joint" v-model="state.ui.selected_joint"><option v-for="j in rig.joints" :value="j.name">{{j.name.replaceAll('_',' ')}}</option></select></label>
     <p class="qd-tip">肩、肘、髋、膝：旋转控制环。手腕、脚踝：在视图平面中拖动 IK 目标。右键转编辑视角。</p>
     <NumberField v-for="(axis,i) in ['X','Y','Z']" :label="`Joint ${axis}`" v-model="selected[i]" :min="-180" :max="180" :step=".1" unit="°" @update:model-value="state.pose.preset='Custom'"/>
     <button class="qd-wide" @click="state.pose.joints[state.ui.selected_joint]=[0,0,0];state.pose.preset='Custom'">Reset joint</button>
    </template>
   </aside>
   <div class="qd-views"><div class="qd-stage-wrap"><div class="qd-viewbar"><span>{{state.ui.view==='stage'?'3D STAGE':'DIRECTOR CAMERA'}}</span><button @click="state.ui.view=state.ui.view==='stage'?'camera':'stage'">{{state.ui.view==='stage'?'Camera view ↗':'Editor view ↗'}}</button></div><div class="qd-stage" ref="host"></div><div class="qd-hint">{{hint}}</div></div>
    <div class="qd-preview-row"><div class="qd-preview"><canvas ref="preview" aria-label="Final pose projection"></canvas></div><div class="qd-preview-info"><span class="qd-eyebrow">FINAL CAMERA PREVIEW</span><h3>最终姿态投影</h3><p>当前摄影机 · 黑底姿态参考</p><dl><dt>Resolution</dt><dd>{{state.render.width}} × {{state.render.height}}</dd><dt>Relative yaw</dt><dd>{{relative}}°</dd><dt>Pose</dt><dd>{{state.pose.preset}}</dd></dl><p class="qd-tip">右键：编辑视角 · 中键：平移</p></div></div>
   </div>
  </div>
  <div v-if="jsonOpen" class="qd-json"><textarea aria-label="Director state JSON" v-model="jsonText" spellcheck="false"></textarea><button @click="importJson">Import state / 导入</button><span>复制 JSON 可保存或批量复用</span></div>
  <div v-if="error" class="qd-error" role="alert">{{error}}</div>
  <footer><span class="qd-status">●</span> Camera · Actor · Pose <span>独立控制 / 工作流自动保存</span></footer>
 </section>
</template>
