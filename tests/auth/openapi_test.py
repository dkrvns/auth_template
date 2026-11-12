from httpx import AsyncClient


async def test_sign_up_from_openapi_example(http_client: AsyncClient) -> None:
    schema_response = await http_client.get('/openapi.json')
    assert schema_response.status_code == 200
    example = schema_response.json()['components']['schemas']['CredentialsRequest'][
        'examples'
    ][0]

    signup = await http_client.post('/auth/signup', json=example)

    assert signup.status_code == 201
    user_id = signup.json()['id']
    login = await http_client.post('/auth/login', json=example)
    assert login.status_code == 200
    profile = await http_client.get(
        '/users/me',
        headers={'Authorization': f'Bearer {login.json()["access_token"]}'},
    )
    assert profile.status_code == 200
    assert profile.json() == {'id': user_id, 'email': example['email']}
