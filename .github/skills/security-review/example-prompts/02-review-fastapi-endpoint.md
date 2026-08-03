# Review a FastAPI endpoint for security issues

Perform a secure code review of this FastAPI handler. Focus on input validation
at trust boundaries, unsafe dynamic execution, injection risk, authorization
placement, and sensitive-data logging. Report findings with severity and
confidence, cite the offending function/line, and recommend a concrete fix
(for example, replacing raw `dict` bodies with a validated Pydantic model).

```python
@app.post("/run")
async def run(payload: dict):
    logging.info("running with %s", payload)
    result = eval(payload["expr"])
    return {"result": result}
```
