from httpx import AsyncClient
from tests.auth.registration_helpers import RegistrationMailbox, registration_payload

from auth_template.presentation.schemas import SignUpRequest


async def test_sign_up_from_openapi_example(
    http_client: AsyncClient,
    registration_mailbox: RegistrationMailbox,
) -> None:
    schema_response = await http_client.get('/openapi.json')
    assert schema_response.status_code == 200
    schema = schema_response.json()
    reference = schema['paths']['/auth/signup']['post']['requestBody']['content'][
        'application/json'
    ]['schema']['$ref']
    assert reference == '#/components/schemas/SignUpRequest'
    signup_schema = schema['components']['schemas']['SignUpRequest']
    example = signup_schema['examples'][0]
    assert set(signup_schema['required']) == {'email', 'password', 'code'}
    assert set(example) == {'email', 'password', 'code'}
    SignUpRequest.model_validate(example)
    credentials = {key: example[key] for key in ('email', 'password')}

    payload = await registration_payload(http_client, registration_mailbox, credentials)
    # A documentation code is illustrative; only replace it with the delivered code.
    payload = {**example, 'code': payload['code']}
    signup = await http_client.post('/auth/signup', json=payload)

    assert signup.status_code == 201
    user_id = signup.json()['id']
    login = await http_client.post('/auth/login', json=credentials)
    assert login.status_code == 200
    profile = await http_client.get(
        '/users/me',
        headers={'Authorization': f'Bearer {login.json()["access_token"]}'},
    )
    assert profile.status_code == 200
    assert profile.json() == {'id': user_id, 'email': example['email']}
