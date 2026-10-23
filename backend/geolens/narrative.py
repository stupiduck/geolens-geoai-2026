"""Readable rendering of retrieved facts and the model's validated comparisons."""
from datetime import datetime

ADVICE={
 'running':'Keep the effort easy, bring water and check access before leaving.',
 'cycling':'Wear a helmet and check the mapped segment and road conditions before riding.',
 'hiking':'Carry water and suitable footwear; confirm the actual trail and terrain before setting out.',
 'golf':'Check course access and booking, and stop if thunder is heard.',
 'cricket':'Check pitch access and surface conditions, and plan hydration breaks.',
 'football':'Check pitch access and surface conditions, and plan hydration breaks.',
 'tennis':'Confirm court access and booking; check for a wet or slippery surface.',
 'picnic':'Check access and available facilities; bring water and take waste home.',
 'outdoor_gathering':'Confirm permissions, access and a weather backup before inviting others.',
 'outdoor_photography':'Check access and actual light conditions; mapped viewpoints are not verified shooting permissions.'}

def render(result,language):
    intent=result.get('normalized_intent',{});activity=intent.get('activity','running')
    if result['status']=='no_suitable_option':
        warnings={c for o in result.get('matrix',[]) for c in o['warning_codes']}
        if 'pollution_avoid_intense_activity' in warnings:
            result['answer']='क्षेत्रीय वायु गुणवत्ता के पूर्वानुमान के कारण इस समय के लिए यह गतिविधि सुझाना उचित नहीं है। कम तीव्रता वाली गतिविधि, इनडोर विकल्प या दूसरा समय चुनें। यह स्थानीय सेंसर का माप नहीं है।' if language=='hi' else 'The regional air-quality forecast makes this a poor window for the requested activity under this planner’s exposure policy. Choose a less intense activity, an indoor option or another time. This is a regional forecast, not a local sensor reading.'
        result['precautions']=[ADVICE.get(activity,ADVICE['running'])]
        return
    if result['status']!='ok':return
    best=result['recommendations'][0];venue=next(v for v in result['venues'] if v['id']==best['venue_id'])
    when=datetime.fromisoformat(best['time']).strftime('%d %b, %H:%M')
    result['summary']=f"{venue['name']} में {when} IST पर जाने पर विचार करें।" if language=='hi' else f"I’d choose {venue['name']} at {when} IST."
    facts=[];c=best['conditions']
    if c.get('temperature') is not None:facts.append(f"{c['temperature']:.0f}°C")
    if c.get('rain_probability') is not None:facts.append(f"बारिश की संभावना {c['rain_probability']:.0f}%" if language=='hi' else f"{c['rain_probability']:.0f}% rain chance")
    forecast=('शुरू के घंटे का पूर्वानुमान: ' if language=='hi' else 'At the start of the activity, the forecast is ')+', '.join(facts)+'.' if facts else ''
    phrases={
        'regional_aq_shared':('The compared locations share the same regional air-quality forecast.','तुलना की गई जगहों के लिए क्षेत्रीय वायु गुणवत्ता का पूर्वानुमान समान है।'),
        'cooler_than':('has a cooler start-hour forecast','के शुरू के घंटे का तापमान कम है'),
        'less_rain_than':('has a lower start-hour rain chance','के शुरू के घंटे में बारिश की संभावना कम है'),
        'cleaner_regional_air':('has lower modeled regional US AQI','का क्षेत्रीय मॉडल वाला US AQI कम है'),
        'lower_thermal_penalty':('has a more comfortable temperature forecast','के तापमान का पूर्वानुमान अधिक अनुकूल है'),
        'lower_road_proxy':('scores better for mapped road and industry proximity','की मानचित्रित सड़क और उद्योग निकटता की तुलना बेहतर है'),
        'shorter_trip':('is closer to your search area','आपके खोज क्षेत्र से अधिक करीब है'),
        'more_mapped_green':('has more mapped woodland nearby','के पास अधिक मानचित्रित वन क्षेत्र है'),
        'higher_score':('scores higher under these planning rules','की इन योजना नियमों के अनुसार उपयुक्तता अधिक है')}
    comparisons=[]
    for item in result.get('explanations',[])[:2]:
        predicate=item['predicate']
        if predicate not in phrases:continue
        if predicate=='regional_aq_shared':comparisons.append(phrases[predicate][language=='hi']);continue
        chosen=(item.get('option_ids') or [None])[0]==best['id']
        subject=('यह विकल्प ' if chosen else 'तुलना किया गया दूसरा विकल्प ') if language=='hi' else ('This option ' if chosen else 'A compared alternative ')
        comparisons.append(subject+phrases[predicate][language=='hi']+'.')
    explanation=' '.join(comparisons)
    caution=''
    if any(w.startswith('pollution_') for w in best['warning_codes']):
        caution='क्षेत्रीय वायु गुणवत्ता बढ़ी हुई है; समय और मेहनत कम रखें।' if language=='hi' else 'Regional air quality is elevated: shorten the outing, reduce effort and take breaks.'
    if c.get('rain_probability',0)>=60:
        caution=('बारिश की संभावना अधिक है। बाहर जाने के बजाय दूसरा समय चुनना बेहतर हो सकता है; जलरोधी आश्रय की पुष्टि करें।' if language=='hi' else 'Rain is likely. Consider another time; this is a relative ranking, not a promise of pleasant weather. Confirm a sheltered backup.')+' '+caution
    advice='पानी और उपयुक्त जूते साथ रखें। जाने से पहले प्रवेश और समय की पुष्टि करें।' if language=='hi' else ADVICE.get(activity,ADVICE['running'])
    result['answer']='\n\n'.join(x for x in [result['summary']+' '+forecast,explanation,caution or advice] if x)
    result['precautions']=list(dict.fromkeys([advice,*result.get('precautions',[])]))
