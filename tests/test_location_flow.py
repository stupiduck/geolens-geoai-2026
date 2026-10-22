import pytest
from geolens.app import Query,run_query,model,sources,no_events


@pytest.mark.asyncio
async def test_commute_clarification_precedes_unknown_activity(monkeypatch):
    async def interpret(_):
        return {'activity':'unknown','language':'hi','commute':True},{}
    monkeypatch.setattr(model,'interpret',interpret)
    result=await run_query(Query(question='कल साइकिल से दफ्तर जाना है'),'test',no_events)
    assert result['status']=='needs_clarification'
    assert result['clarification']['fields']==['origin','destination']


@pytest.mark.asyncio
async def test_selected_location_keeps_original_hindi_question(monkeypatch):
    question='कल सुबह रामपुर में दौड़ना है'
    async def interpret(_):
        return {'activity':'running','language':'hi','location':'रामपुर','time_expression':'कल सुबह'},{}
    async def venues(*_):return [],{}
    async def geocode(_):raise AssertionError('Selected coordinates must not be geocoded again')
    monkeypatch.setattr(model,'interpret',interpret)
    monkeypatch.setattr(sources,'venues',venues)
    monkeypatch.setattr(sources,'geocode',geocode)
    result=await run_query(Query(question=question,location={'id':'relation/42','name':'रामपुर','latitude':28.8,'longitude':79.0}),'test',no_events)
    assert result['input']['question']==question
    assert result['input']['language']=='hi'
    assert result['input']['selected_location']['id']=='relation/42'
    assert result['location']['latitude']==28.8
