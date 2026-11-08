import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {materialize,rank,csv} from './dist/analysis.js';
const root=path.dirname(fileURLToPath(import.meta.url));
const checks=JSON.parse(fs.readFileSync(process.argv[2]));
let segmentComparisons=0;
for(const check of checks){
 const bundle=JSON.parse(fs.readFileSync(path.join(root,'dist/assets',`evidence-${check.bundle}.json`)));
 const rows=materialize(bundle,check.minimum,check.coverage,'test-fingerprint');
 assert.equal(rows.length,check.rows.length);
 const key=r=>JSON.stringify([r.neighbourhood,r.room_type,r.bedroom_segment]);
 const actual=new Map(rows.map(r=>[key(r),r]));
 for(const expected of check.rows){
  const row=actual.get(key(expected));assert.ok(row);
  for(const [field,v] of Object.entries(expected)){
   if(typeof v==='number')assert.ok(Math.abs(row[field]-v)<=1e-10*Math.max(1,Math.abs(v)),`${field}: ${row[field]} vs ${v}`);
   else assert.equal(row[field],v,`${field} in ${key(expected)}`);
  }
  segmentComparisons++;
 }
 const ranked=rank(rows);
 assert.deepEqual(ranked.map(r=>[r.neighbourhood,r.room_type,r.bedroom_segment]),check.ranked);
 assert.ok(csv(ranked,[...bundle.columns,'canonical_fingerprint']).includes('warnings'));
 if(check.bundle==='0-0'&&check.minimum===20&&check.coverage===.8)assert.equal(ranked.length,319);
 const malibu=rows.find(r=>r.neighbourhood==='Malibu'&&r.room_type==='Entire home/apt'&&r.bedroom_segment==='3 bedroom');
 if(check.bundle==='0-0'&&check.minimum===20)assert.equal(malibu.warnings.includes('March local price coverage'),check.coverage===.8);
 const altadena=rows.find(r=>r.neighbourhood==='Altadena'&&r.room_type==='Entire home/apt'&&r.bedroom_segment==='3 bedroom');
 if(check.bundle==='0-0'){assert.equal(altadena.is_small_sample_june,false);if(check.minimum===30){assert.equal(altadena.premium_pct_june,null);assert.ok(altadena.premium_unavailable_reason_june.includes('30'));}}
}
console.log(JSON.stringify({status:'passed',filter_and_threshold_cases:checks.length,segmentComparisons,scope:'12 stay/source bundles × 3 evidence settings; Python/browser medians, coverage, premiums, statuses, fixed flags and complete rank order; CSV headers and targeted warning cases'},null,2));
