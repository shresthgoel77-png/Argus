from fastapi import APIRouter, HTTPException
import razorpay
import os
import uuid
from pydantic import BaseModel

router = APIRouter(prefix="/payments", tags=["payments"])

class CreateOrderRequest(BaseModel):
    amount: int  # in paise
    currency: str = "INR"

@router.post("/create_order")
async def create_order(req: CreateOrderRequest):
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise HTTPException(status_code=500, detail="Razorpay keys not configured")
        
    client = razorpay.Client(auth=(key_id, key_secret))
    
    try:
        order_data = {
            "amount": req.amount,
            "currency": req.currency,
            "receipt": f"receipt_{uuid.uuid4().hex[:8]}"
        }
        order = client.order.create(data=order_data)
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
