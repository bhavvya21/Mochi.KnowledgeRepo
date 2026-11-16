"""Source-bound arithmetic. Never evaluate model-produced code."""
from decimal import Decimal, InvalidOperation
import re
from typing import Literal
from pydantic import BaseModel, Field
from .schema import Evidence


class Operand(Evidence):
    value: str = Field(max_length=40)


class Calculation(BaseModel):
    label: str = Field(max_length=150)
    operation: Literal["sum","difference","product","ratio"]
    operands: list[Operand] = Field(min_length=2,max_length=8)
    unit: str = Field(max_length=30)


class Calculations(BaseModel):
    calculations: list[Calculation] = Field(max_length=4)


def calculate(proposals, hits):
    results=[]
    for proposal in proposals:
        values=[]
        try:
            for operand in proposal.operands:
                if operand.source>len(hits):raise ValueError()
                if ' '.join(operand.quote.split()) not in ' '.join(hits[operand.source-1]["text"].split()):raise ValueError()
                value=Decimal(operand.value.replace(",",""))
                numbers={Decimal(n.replace(",","")) for n in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?!\w|\.\d)",operand.quote)}
                if not value.is_finite() or value not in numbers:raise ValueError()
                values.append(value)
            if proposal.operation=="sum":value=sum(values)
            elif proposal.operation=="product":
                value=Decimal(1)
                for number in values:value*=number
            else:
                if len(values)!=2:raise ValueError()
                value=values[0]-values[1] if proposal.operation=="difference" else values[0]/values[1]
            if not value.is_finite() or abs(value)>Decimal("1e20"):raise ValueError()
            results.append({**proposal.model_dump(),"result":format(value.quantize(Decimal(".01")),"f"),"method":"decimal arithmetic on quoted operands"})
        except (ValueError,InvalidOperation,ZeroDivisionError):continue
    return results
