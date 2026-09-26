#!/usr/bin/env python3
"""
Test file for automatic review workflow
This file has intentional quality issues to test Code Reviewer
"""

def calculate_total(items):
    # Input validation added
    if items is None or not isinstance(items, (list, tuple)):
        raise ValueError("items must be a list or tuple")

    total = 0
    for item in items:
        # Validate item structure
        if not isinstance(item, dict):
            continue

        price = item.get('price', 0)
        quantity = item.get('quantity', 0)

        # Skip invalid values
        if price <= 0 or quantity <= 0:
            continue

        discount = item.get('discount', 0)
        total += price * quantity * (1 - discount)

    return total


# Duplicate code removed - now uses calculate_total
def calculate_subtotal(items):
    # Delegate to calculate_total to avoid code duplication
    return calculate_total(items)


# Long method (>50 lines - intentional)
def process_order(order_data):
    # Input validation added
    if not isinstance(order_data, dict):
        raise ValueError("order_data must be a dict")

    if 'customer' not in order_data or 'items' not in order_data:
        raise ValueError("order_data must contain 'customer' and 'items' keys")

    customer = order_data['customer']
    items = order_data['items']

    # Calculate totals
    subtotal = 0
    tax = 0
    shipping = 0

    for item in items:
        price = item.get('price', 0)
        qty = item.get('quantity', 0)
        subtotal += price * qty

    # Tax calculation with default case
    state = customer.get('state', '').upper()
    if state == 'CA':
        tax = subtotal * 0.0725
    elif state == 'NY':
        tax = subtotal * 0.08
    elif state == 'TX':
        tax = subtotal * 0.0625
    else:
        # Default: no tax for other states (explicit zero)
        tax = 0

    # Shipping calculation with safe key access
    if subtotal > 100:
        shipping = 0
    elif customer.get('prime', False):  # Safe access with default False
        shipping = 0
    else:
        shipping = 9.99

    total = subtotal + tax + shipping

    return total
