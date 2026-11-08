// Canonical backend metrics are exported at minimum 1; higher settings only gate evidence.
export const BEDROOMS=['Studio','1 bedroom','2 bedroom','3 bedroom','4 bedroom','5 bedroom','6+ bedrooms'];
export const STATUSES=['Persistent premium','Persistent discount','Reversed','Neutral','Insufficient evidence'];
export const finite=x=>typeof x==='number'&&Number.isFinite(x);
export function materialize(bundle,minimum=20,coverage=.8,fingerprint='') {
  return bundle.rows.map(values=>{
    const r=Object.fromEntries(bundle.columns.map((c,i)=>[c,values[i]]));
    const notes=[];
    for(const d of ['march','june']) {
      const date=d==='march'?'March':'June';
      if(r['listing_rows_'+d]===null){r['sufficient_data_'+d]=null;r['premium_pct_'+d]=null;r['premium_unavailable_reason_'+d]=null;notes.push(`${date}: segment absent; evidence unavailable.`);continue;}
      r['sufficient_data_'+d]=finite(r['median_price_usd_'+d])&&r['priced_rows_'+d]>=minimum&&r['peer_priced_rows_'+d]>=minimum&&r['peer_median_price_usd_'+d]>0;
      if(!r['sufficient_data_'+d])r['premium_pct_'+d]=null;
      r['premium_unavailable_reason_'+d]=r['sufficient_data_'+d]?'':`Local and peer each need at least ${minimum} valid prices and a positive peer median.`;
      for(const [prefix,pop] of [['','local'],['peer_','peer']]){
        const cov=r[prefix+'price_coverage_'+d];
        if(finite(cov)&&cov<coverage)notes.push(`${date} ${pop} price coverage ${(cov*100).toFixed(1)}% is below the ${(coverage*100).toFixed(0)}% warning threshold.`);
        if(r[prefix+'is_small_sample_'+d])notes.push(`${date} ${pop}: small sample (<20 priced listings).`);
      }
      if(!r['sufficient_data_'+d])notes.push(`${date}: premium fails current minimum evidence requirement.`);
      for(const pop of ['local','peer']){
        const share=r[pop+'_unknown_bedroom_share_'+d];
        if(finite(share)&&share>=.25)notes.push(`${date} ${pop}: bedroom completeness warning; ${(share*100).toFixed(1)}% unknown bedrooms excluded.`);
      }
      const local=r['previous_scrape_share_'+d],peer=r['peer_previous_scrape_share_'+d];
      if(local>0||peer>0)notes.push(`${date} source caution: previous-scrape share local ${(local*100).toFixed(1)}%, peer ${(peer*100).toFixed(1)}%; nominal dates may differ from scrape dates.`);
      if(r['unknown_source_share_'+d]>0||r['peer_unknown_source_share_'+d]>0)notes.push(`${date}: source category is unavailable for some listings.`);
    }
    for(const pop of ['local','peer']){
      const m=r[pop+'_unknown_bedroom_share_march'],j=r[pop+'_unknown_bedroom_share_june'];
      if(finite(m)&&finite(j)&&j-m>=.10)notes.push(`${pop==='local'?'Local':'Peer'} bedroom completeness deteriorated by ${((j-m)*100).toFixed(1)} percentage points; composition may distort comparison.`);
    }
    if(r.bedroom_segment==='Studio')notes.push('Studio coding warning: recorded zeros and missing bedrooms change sharply between snapshots; do not interpret this as supply change.');
    if(!r.sufficient_data_march||!r.sufficient_data_june){r.persistence_status='Insufficient evidence';r.direction='Unavailable';r.review_score=null;}
    r.minimum_priced=minimum;r.coverage_warning_threshold=coverage;r.canonical_fingerprint=fingerprint;
    r.warnings=notes.join(' | ')||'No row-specific quality warning at current settings.';
    return r;
  });
}
export function rank(rows,direction='Both'){
  return rows.filter(r=>['Persistent premium','Persistent discount'].includes(r.persistence_status)&&(direction==='Both'||r.direction===direction)).sort((a,b)=>b.review_score-a.review_score||(a.neighbourhood<b.neighbourhood?-1:a.neighbourhood>b.neighbourhood?1:0)||(a.room_type<b.room_type?-1:a.room_type>b.room_type?1:0)||BEDROOMS.indexOf(a.bedroom_segment)-BEDROOMS.indexOf(b.bedroom_segment)).map((r,i)=>({...r,rank:i+1}));
}
export function csv(rows,columns){
  columns=columns||Object.keys(rows[0]||{});
  const quote=v=>v===null||v===undefined?'':`"${String(v).replaceAll('"','""')}"`;
  return '\uFEFF'+columns.map(quote).join(',')+'\r\n'+rows.map(r=>columns.map(c=>quote(r[c])).join(',')).join('\r\n');
}
