import requests
import json

def fetch_products():
    """
    Fetches all live products from carezone.pk.
    Equivalent to shopifySync.js in the Node project.
    """
    print("Fetching ALL live products from Carezone.pk...")
    all_products = []
    page = 1
    has_more = True

    while has_more:
        url = f"https://carezone.pk/products.json?limit=250&page={page}"
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()

            if not data or "products" not in data or len(data["products"]) == 0:
                has_more = False
                break

            for p in data["products"]:
                variant = p["variants"][0] if p["variants"] else {}
                all_products.append({
                    "name": p["title"],
                    "price": variant.get("price", "Unknown"),
                    "in_stock": variant.get("available", False)
                })

            page += 1
            # Safety break to prevent infinite loops
            if page > 30:
                break

        except Exception as e:
            print(f"Error fetching products from Shopify: {e}")
            break

    print(f"Successfully fetched {len(all_products)} TOTAL products.")
    return all_products

if __name__ == "__main__":
    products = fetch_products()
    if products:
        print(f"Sample product: {products[0]}")
