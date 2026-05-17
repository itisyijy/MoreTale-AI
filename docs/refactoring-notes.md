# MoreTale-AI Refactoring Notes

## Internal AI request schema warnings

The internal AI request models use camelCase aliases because the backend contract
expects fields such as `callbackUrl`, `requestId`, `storyId`, `storyJsonUrl`,
`questionCount`, `textKr`, and `textNative`.

During Python 3.14 test runs, FastAPI/Pydantic can emit
`UnsupportedFieldAttributeWarning` while handling request body models with field
aliases. The remaining warning is produced inside FastAPI's request-body field
extraction path, where model fields are wrapped again as `Annotated[..., FieldInfo]`.

The story internal request model was simplified from multiple inheritance to a
single request-model inheritance shape. The remaining warning was not suppressed
in application code because removing aliases would change the public JSON and
OpenAPI contract. Use test pass/fail output as the behavior baseline until the
FastAPI/Pydantic/Python 3.14 compatibility path is resolved upstream or dependency
versions are updated.
