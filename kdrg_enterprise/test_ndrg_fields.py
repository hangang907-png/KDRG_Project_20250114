
import asyncio
import httpx

async def test_ndrg_fields():
    api_key = "3bdd9d35b0a44e615fe80ca653d7265b3ce463b24485a368d3d6748ad7bbb224"
    url = "http://apis.data.go.kr/B551182/NdrgStdInfoService/getNdrgStdInfo"
    params = {
        "serviceKey": api_key,
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ndrg_fields())
