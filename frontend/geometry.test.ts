import { describe,it,expect } from 'vitest';
import { Vector3 } from 'three';
import fixtures from '../tests/projection-fixtures.json';
import { defaults,deserialize,preset,rig,wrap } from './state';
import { makeRig,updateRig,project,worldPoints } from './three/geometry';
import { solveIK } from './three/pose';

describe('Director geometry contract',()=>{
 it('normalizes angles and round trips state',()=>{
   expect([-10,370,720].map(wrap)).toEqual([350,10,0]);
   const s=defaults();preset(s,'Asymmetric');expect(deserialize(JSON.stringify(s))).toEqual(s);
   expect(()=>deserialize('{"version":2}')).toThrow();
   expect(()=>deserialize('{"actor":{"scale":0}}')).toThrow();
 });
 it('matches Python world projection for eight views with actor transforms and camera roll',()=>{
   for(const fixture of fixtures) {
     const s=deserialize(fixture.state),r=makeRig();updateRig(r,s);const p=project(s,r);
     for(const [name,expected] of Object.entries(fixture.points)) {
       expect(p[name].xy[0]).toBeCloseTo(expected.xy[0],7);expect(p[name].xy[1]).toBeCloseTo(expected.xy[1],7);
       expect(p[name].depth).toBeCloseTo(expected.depth,10);expect(p[name].visible).toBe(expected.visible);
     }
   }
 });
 it('two-bone IK preserves lengths, parent transforms and camera for reachable and unreachable targets',()=>{
   for(const name of ['left_wrist','right_wrist','left_ankle','right_ankle'])for(const target of [[.3,1.2,.2],[4,8,4],[0,.94,0]]) {
     const s=defaults();s.actor.yaw=31;s.actor.pitch=17;s.actor.scale=1.2;
     const before=JSON.stringify({camera:s.camera,actor:s.actor}),r=makeRig();updateRig(r,s);
     solveIK(r,s,name,new Vector3(...target));const points=worldPoints(r);
     expect(JSON.stringify({camera:s.camera,actor:s.actor})).toBe(before);
     for(const j of rig.joints)if(j.parent)expect(points[j.name].distanceTo(points[j.parent])).toBeCloseTo(new Vector3(...j.offset).length()*s.actor.scale,9);
     for(const v of Object.values(s.pose.joints))expect(v.every(Number.isFinite)).toBe(true);
   }
 });
 it('IK reaches an in-range wrist target',()=>{
   const s=defaults(),r=makeRig();updateRig(r,s);const target=new Vector3(-.3,1.2,.3);
   solveIK(r,s,'right_wrist',target);expect(worldPoints(r).right_wrist.distanceTo(target)).toBeLessThan(1e-8);
 });
});
