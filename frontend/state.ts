import rigData from '../shared/rig.json';
export type Vec3 = [number, number, number];
export type Mode = 'CAMERA' | 'ACTOR' | 'POSE';
export interface DirectorState {
  version: 1;
  camera: { azimuth: number; elevation: number; distance: number; fov: number; roll: number; target: Vec3 };
  actor: { position: Vec3; yaw: number; pitch: number; roll: number; scale: number };
  pose: { skeleton_type: string; preset: string; joints: Record<string, Vec3> };
  render: { width: number; height: number; background: 'black' };
  ui: { mode: Mode; selected_joint: string; view: 'stage' | 'camera' };
}
export const rig = rigData;
export const NEAR = .05, FAR = 200;
export const RAD = Math.PI / 180;
export const wrap = (v: number) => ((v % 360) + 360) % 360;
export const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));
export function defaults(): DirectorState {
  return {
    version: 1,
    camera: { azimuth: 0, elevation: 0, distance: 3.1, fov: 40, roll: 0, target: [0,.95,0] },
    actor: { position: [0,0,0], yaw: 0, pitch: 0, roll: 0, scale: 1 },
    pose: { skeleton_type: 'director_body_v1', preset: 'Neutral Standing', joints: Object.fromEntries(rig.joints.map(j => [j.name, [0,0,0] as Vec3])) },
    render: { width: 1024, height: 1024, background: 'black' },
    ui: { mode: 'CAMERA', selected_joint: 'right_shoulder', view: 'stage' },
  };
}
export function deserialize(raw: string | object): DirectorState {
  if (typeof raw === 'string' && raw.length > 100000) throw Error('Director state is too large');
  const data = typeof raw === 'string' ? JSON.parse(raw || '{}') : raw;
  if (!data || Array.isArray(data) || typeof data !== 'object') throw Error('State must be an object');
  if (data.version !== undefined && data.version !== 1) throw Error('Unsupported state version');
  const s = defaults();
  for (const key of ['camera','actor','pose','render','ui'] as const) {
    if (data[key] !== undefined && (!data[key] || Array.isArray(data[key]) || typeof data[key] !== 'object')) throw Error(`Invalid ${key}`);
    Object.assign(s[key], data[key] || {});
  }
  const n = (v: unknown, lo: number, hi: number): number => {
    if (typeof v !== 'number' || !Number.isFinite(v) || v < lo || v > hi) throw Error(`Number outside ${lo}…${hi}`);
    return v;
  };
  const vector = (v: unknown, limit: number): Vec3 => {
    if (!Array.isArray(v) || v.length !== 3) throw Error('Expected XYZ vector');
    return v.map(x => n(x,-limit,limit)) as Vec3;
  };
  const c=s.camera,a=s.actor,p=s.pose,r=s.render;
  c.azimuth=wrap(n(c.azimuth,-1e6,1e6)); c.elevation=n(c.elevation,-89,89);
  c.distance=n(c.distance,.2,50); c.fov=n(c.fov,10,120); c.roll=n(c.roll,-180,180); c.target=vector(c.target,50);
  a.position=vector(a.position,50); a.scale=n(a.scale,.1,5);
  for (const k of ['yaw','pitch','roll'] as const) a[k]=n(a[k],-1e6,1e6);
  if (p.skeleton_type !== 'director_body_v1' || !p.joints || Array.isArray(p.joints) || typeof p.joints !== 'object') throw Error('Invalid skeleton');
  if (Object.keys(p.joints).some(k => !rig.joints.some(j => j.name===k))) throw Error('Unknown joint');
  p.joints=Object.fromEntries(rig.joints.map(j => [j.name,vector(p.joints[j.name] || [0,0,0],36000)]));
  if (typeof p.preset !== 'string' || p.preset.length > 80) throw Error('Invalid preset');
  for (const k of ['width','height'] as const) { n(r[k],64,2048); if (!Number.isInteger(r[k])) throw Error('Dimensions must be integers'); }
  if (r.background !== 'black') throw Error('Pose control background must be black');
  if (!['CAMERA','ACTOR','POSE'].includes(s.ui.mode) || !['stage','camera'].includes(s.ui.view) || !p.joints[s.ui.selected_joint]) throw Error('Invalid editor state');
  return clone(s);
}
export function preset(s: DirectorState, name: string) {
  const values = (rig.presets as Record<string,Record<string,number[]>>)[name];
  if (!values) throw Error('Unknown preset');
  s.pose.joints=Object.fromEntries(rig.joints.map(j=>[j.name,(values[j.name] || [0,0,0]).slice() as Vec3]));
  s.pose.preset=name;
}
