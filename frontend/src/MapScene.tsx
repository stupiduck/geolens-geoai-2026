import {useEffect,useRef} from 'react';
import * as maplibregl from 'maplibre-gl';
import {Map, Marker} from 'maplibre-gl';
import type {Venue,Option} from './types';

export default function MapScene({venues,selected,options,onSelect,layers,showLayers}:{venues:Venue[];selected:string|null;options:Option[];onSelect:(id:string)=>void;layers?:GeoJSON.FeatureCollection;showLayers:boolean}){
  const container=useRef<HTMLDivElement>(null),map=useRef<Map|null>(null),markers=useRef<Marker[]>([]);
  const callback=useRef(onSelect);callback.current=onSelect;
  useEffect(()=>{
    if(!container.current)return;
    const m=new Map({container:container.current,style:'https://tiles.openfreemap.org/styles/positron',center:[72.918,19.113],zoom:11.7,attributionControl:{compact:false},maxPitch:45});
    map.current=m;
    m.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
    m.addControl(new maplibregl.ScaleControl({unit:'metric'}),'bottom-right');
    m.on('load',()=>{
      for(const layer of m.getStyle().layers){
        if(layer.type==='fill' && layer.id.toLowerCase().includes('water'))m.setPaintProperty(layer.id,'fill-color','#a8c9cb');
        if(layer.type==='background')m.setPaintProperty(layer.id,'background-color','#eaece2');
      }
    });
    m.on('error',()=>{container.current?.setAttribute('data-map-error','Map tiles may be unavailable; the result list remains usable.');});
    return()=>{m.remove();map.current=null};
  },[]);
  useEffect(()=>{
    const m=map.current;if(!m)return;
    markers.current.forEach(marker=>marker.remove());
    const ranked=[...options].sort((a,b)=>b.score-a.score);
    markers.current=venues.map(v=>{
      const option=options.find(o=>o.venue_id===v.id),rank=ranked.findIndex(o=>o.venue_id===v.id)+1;
      const button=document.createElement('button');
      button.className=`venue-marker ${v.id===selected?'selected':''} ${option?.eligibility==='avoid'?'avoid':''}`;
      button.textContent=String(rank||'·');button.setAttribute('aria-label',`Select ${v.name}`);
      button.addEventListener('click',()=>callback.current(v.id));
      return new Marker({element:button}).setLngLat([v.lon,v.lat]).addTo(m);
    });
  },[venues,selected,options]);
  const lastVenueKey=useRef('');
  useEffect(()=>{
    const m=map.current;if(!m||!venues.length)return;
    const key=venues.map(v=>v.id).join();if(lastVenueKey.current===key)return;lastVenueKey.current=key;
    const bounds=new maplibregl.LngLatBounds();venues.forEach(v=>bounds.extend([v.lon,v.lat]));
    m.fitBounds(bounds,{padding:window.innerWidth>800?{left:420,right:100,top:110,bottom:260}:70,maxZoom:14,duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:800});
  },[venues]);
  useEffect(()=>{
    const m=map.current;if(!m)return;
    const apply=()=>{
      if(m.getLayer('geo-context'))m.removeLayer('geo-context');
      if(m.getSource('geo-context'))m.removeSource('geo-context');
      if(!layers||!showLayers)return;
      m.addSource('geo-context',{type:'geojson',data:layers});
      m.addLayer({id:'geo-context',type:'line',source:'geo-context',paint:{'line-color':['match',['get','kind'],'roads','#b38b5c','industry','#a6614c','water','#287685','#56816a'],'line-width':2,'line-opacity':.65}});
    };
    if(m.isStyleLoaded())apply();else m.once('load',apply);
    return()=>{m.off('load',apply)};
  },[layers,showLayers]);
  return <div ref={container} className="map" role="region" aria-label="Interactive geographic map. Equivalent venue results appear in the list."/>;
}
