'''
group_balance_list ->

{
    userid1 -> amount pay or take ie -10 or +10),
    userid2 -> amount pay or take ie -10 or +10),
    
}

groupGraph ->
{
    'useridA' -> [ ['useridB',+ or - amount]] # if + then useridA get back amount from useridB, else useridA has to pay to useridB.
    'useridB' -> ... same
}
'''
from decimal import Decimal


def update_group_balances(group_data, payer_id, receiver_id, amount):
    """
    Updates the 'groupBalance' ledger (The Source of Truth).
    """
    if(payer_id == receiver_id): return
    group_balance_list = group_data.setdefault('groupBalance', {})
    
    # Use Decimal for math to avoid 99.9999999 bugs
    p_bal = Decimal(str(group_balance_list.get(payer_id, 0)))
    r_bal = Decimal(str(group_balance_list.get(receiver_id, 0)))
    amt = Decimal(str(amount))

    group_balance_list[payer_id] = float(p_bal + amt)
    group_balance_list[receiver_id] = float(r_bal - amt)
    
    


def optimal_account_balance(group_data):
    """
    Greedy Algorithm to minimize transactions.
    Rebuilds 'groupGraph' from 'groupBalance'.
    """
    group_balance_list = group_data.setdefault('groupBalance', {})

    positive_accounts = []
    negative_accounts = []
    
    for userid, balance in group_balance_list.items():
        if balance > 0:
            positive_accounts.append([Decimal(str(balance)), userid])
        elif balance < 0:
            negative_accounts.append([Decimal(str(balance)), userid])
            
    # As per your request: Settle smallest balances first
    positive_accounts.sort(key=lambda x: x[0]) 
    negative_accounts.sort(key=lambda x: x[0], reverse=True) 

    # Initialize new graph with empty maps for every member
    new_graph = {uid: {} for uid in group_data.get('groupMembers', [])}
    
    i = 0
    j = 0
    while i < len(positive_accounts) and j < len(negative_accounts):
        pos_balance = positive_accounts[i][0]
        neg_balance = abs(negative_accounts[j][0])
        pos_owner = positive_accounts[i][1]
        neg_owner = negative_accounts[j][1]
        
        net_amount = min(pos_balance, neg_balance)
        
        if net_amount > 0:
            # Bidirectional entries for easy Android lookup
            # matches: Map<String, Map<String, Double>>
            new_graph[pos_owner][neg_owner] = float(net_amount)
            new_graph[neg_owner][pos_owner] = float(-net_amount)
            
        # Update temporary list for math
        positive_accounts[i][0] -= net_amount
        negative_accounts[j][0] += net_amount
        
        if positive_accounts[i][0] == 0: i += 1
        if negative_accounts[j][0] == 0: j += 1

    group_data['groupGraph'] = new_graph
    
    if((i< len(positive_accounts)) or( j<len(negative_accounts)) ):
        print("something wrong account is not balance fully")
