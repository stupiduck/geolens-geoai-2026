import {useEffect,useRef} from 'react';
import * as maplibregl from 'maplibre-gl';
import {Map, Marker} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
maplibregl.setWorkerUrl(workerUrl);
import type {Venue,Option} from './types';
import {imagery} from './imagery';

export default function MapScene({venues,selected,options,onSelect,layers,showLayers,satellite}:{venues:Venue[];selected:string|null;options:Option[];onSelect:(id:string)=>void;layers?:GeoJSON.FeatureCollection;showLayers:boolean;satellite:boolean}){
  const container=useRef<HTMLDivElement>(null),map=useRef<Map|null>(null),markers=useRef<Marker[]>([]);
  const callback=useRef(onSelect);callback.current=onSelect;
  useEffect(()=>{
    if(!container.current)return;
    const m=new Map({container:container.current,style:'https://tiles.openfreemap.org/styles/positron',center:[79,22],zoom:4.2,attributionControl:{},canvasContextAttributes:{preserveDrawingBuffer:true},maxPitch:45});
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
    const apply=()=>{
      if(!m.getSource('satellite')){
        m.addSource('satellite',{type:'raster',tiles:imagery.tiles,tileSize:256,maxzoom:imagery.maxzoom,attribution:imagery.attribution});
        const firstLabel=m.getStyle().layers.find(l=>l.type==='symbol')?.id;
        m.addLayer({id:'satellite',type:'raster',source:'satellite',layout:{visibility:'none'}},firstLabel);
      }
      m.setLayoutProperty('satellite','visibility',satellite?'visible':'none');
    };
    if(m.isStyleLoaded())apply();else m.once('load',apply);
    return()=>{m.off('load',apply)};
  },[satellite]);
  useEffect(()=>{
    const m=map.current;if(!m)return;
    markers.current.forEach(marker=>marker.remove());
    markers.current=venues.map((v,index)=>{
      const option=options.find(o=>o.venue_id===v.id),rank=index+1;
      const button=document.createElement('button');
      button.className=`venue-marker ${v.id===selected?'selected':''} ${option?.eligibility==='avoid'?'avoid':''}`;
      button.textContent=String(rank||'·');button.setAttribute('aria-label',`Select ${v.name}`);
      button.addEventListener('click',()=>callback.current(v.id));
      return new Marker({element:button}).setLngLat([v.lon,v.lat]).addTo(m);
    });
    m.resize();m.triggerRepaint();
  },[venues,selected,options]);
  useEffect(()=>{
    const m=map.current;if(!m||!venues.length)return;
    const bounds=new maplibregl.LngLatBounds();venues.forEach(v=>bounds.extend([v.lon,v.lat]));
    const fit=()=>{if(m.getContainer().clientWidth<100||m.getContainer().clientHeight<100)return;m.fitBounds(bounds,{padding:60,maxZoom:14,duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:500})};
    fit();
    const observer=new ResizeObserver(()=>{m.resize();fit();m.triggerRepaint()});
    observer.observe(m.getContainer());
    return()=>observer.disconnect();
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
