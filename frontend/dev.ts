import { createApp } from 'vue';
import DirectorWidget from './components/DirectorWidget.vue';
import './style.css';
createApp(DirectorWidget,{initial:localStorage.getItem('qwen-director-dev')||'{}',onChange:(v:string)=>localStorage.setItem('qwen-director-dev',v)}).mount('#app');
