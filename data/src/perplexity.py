import requests
import json
import os
from dotenv import load_dotenv
import aiohttp
import asyncio

# Load environment variables
load_dotenv()

async def query_perplexity_async(prompt, max_tokens=4000):
    API_URL = "https://api.perplexity.ai/chat/completions"
    API_KEY = os.getenv("PERPLEXITY_API_KEY")
    
    if not API_KEY:
        raise ValueError("PERPLEXITY_API_KEY not found in environment variables")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-sonar-huge-128k-online",
        "messages": [
            {"role": "system", "content": "You are a specialized web scraping assistant for FPV drone parts."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=headers, json=payload) as response:
                response.raise_for_status()
                content = await response.json()
                content = content['choices'][0]['message']['content']
                
                # Remove ```json and ``` from the response
                content = content.replace("```json", "").replace("```", "").strip()
                
                return content
    except aiohttp.ClientError as e:
        print(f"Error communicating with Perplexity API: {str(e)}")
        return None

def query_perplexity(prompt, max_tokens=4000):
    return asyncio.get_event_loop().run_until_complete(query_perplexity_async(prompt, max_tokens))

def generate_product_prompt(product_name, category, category_fields):
    prompt = f"""
    You are a specialized web scraping assistant tasked with gathering detailed information about {category} for FPV drones. 
    Given the product title "{product_name}", search the web for comprehensive details about the {category} and organize the information into the following JSON structure:

    {{
      "name": "string (full product name)",
      "category": "{category}",
      "shortDescription": "string (1-2 sentence description)",
      "fullDescription": "string (detailed description)",
      "price": float (in USD),
      "image": "string (URL to product image)",
      "specifications": {{
        // Include relevant specifications based on the category, most notably weight, dimensions. Do not repeat or be redundant with the compatibility tags. The compatibility tags are more important.
      }},
      "compatibilityTags": {{
    """

    for tag_category, possible_values in category_fields.items():
        prompt += f'    "{tag_category}": ["string" or null],\n'

    prompt += """
      },
      "links": {
        "Amazon": {"url": "string (Amazon product URL)", "price": float or null},
        "GetFPV": {"url": "string (GetFPV product URL)", "price": float or null},
        "(Additional names encountered)": {"url": "string (any additional URLs)", "price": float or null}
      }
    }

    Ensure all information is accurate and up-to-date. If certain information is not available, use null for that field.
    If you encounter multiple versions or variations of the {category}, focus on the most popular or latest version, unless the product title specifies a particular variant.

    For the compatibilityTags, use the following options for each category:
    """

    for tag_category, possible_values in category_fields.items():
        prompt += f'    {tag_category}: {json.dumps(possible_values)}\n'

    prompt += """
    Only include tags that are relevant to the product. If a tag is not applicable or the information is not available, use null.

    Please provide the completed JSON object based on your web scraping results for the given {category} title.
    Only output the JSON object, nothing else. Ensure the output is valid JSON.
    """

    return prompt