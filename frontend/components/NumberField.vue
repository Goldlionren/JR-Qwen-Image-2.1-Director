<script setup lang="ts">
const props=defineProps<{label:string;modelValue:number;min:number;max:number;step?:number;unit?:string}>();
const emit=defineEmits<{'update:modelValue':[number]}>();
function change(e:Event) {const v=Number((e.target as HTMLInputElement).value);if(Number.isFinite(v))emit('update:modelValue',Math.max(props.min,Math.min(props.max,v)));}
</script>
<template>
  <label class="qd-number"><span>{{label}} <small>{{unit}}</small></span><input type="number" :aria-label="label" :value="Number(modelValue.toFixed(3))" :min="min" :max="max" :step="step??1" @input="change"/><input type="range" :aria-label="`${label} slider`" :value="modelValue" :min="min" :max="max" :step="step??1" @input="change"/></label>
</template>
