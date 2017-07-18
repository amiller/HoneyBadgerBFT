from ethereum.transactions import Transaction
import rlp
from rlp.sedes import CountableList

def decode(payload):
    return rlp.decode(payload, CountableList(Transaction))

def encode(txes):
    return rlp.encode(txes)
