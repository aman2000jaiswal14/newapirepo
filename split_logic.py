from decimal import Decimal, ROUND_HALF_UP

def update_group_graph(group_data, payer_id, receiver_id, amount):
    """
    Mathematical core of the splitting engine.
    Uses Decimal to prevent floating point errors (e.g., 0.000000004).
    """
    if receiver_id == payer_id or amount == 0:
        return
    
    # Convert input to Decimal for safe math
    amt_to_add = Decimal(str(amount))
    
    # Ensure nested structures exist
    graph = group_data.setdefault('groupGraph', {})
    payer_map = graph.setdefault(payer_id, {})
    receiver_map = graph.setdefault(receiver_id, {})
    
    # current_debt is what payer_id is currently owed by receiver_id
    current_direct_debt = Decimal(str(payer_map.get(receiver_id, 0)))
    
    # total_to_process is the new total debt to resolve
    total_to_process = amt_to_add + current_direct_debt
    payer_map[receiver_id] = 0 # Temporarily zero out to recalculate flow

    members = group_data.get('groupMembers', [])

    # STEP 1: Triangular Simplification
    # If Receiver owes money to others, Payer can take over those debts.
    for m_id in members:
        if total_to_process <= 0: break
        if m_id == receiver_id: continue
        
        debt_receiver_owes_m = Decimal(str(receiver_map.get(m_id, 0)))
        if debt_receiver_owes_m > 0:
            flow = min(total_to_process, debt_receiver_owes_m)
            receiver_map[m_id] = float(debt_receiver_owes_m - flow)
            
            if m_id != payer_id:
                # Payer now collects this from m_id instead of receiver collecting it
                payer_map[m_id] = float(Decimal(str(payer_map.get(m_id, 0))) + flow)
            total_to_process -= flow

    # STEP 2: Reverse Debt Simplification
    # If others owe money to the Payer, they can pay the Receiver instead.
    for m_id in members:
        if total_to_process <= 0: break
        if m_id == payer_id: continue
        
        others_owe_payer = Decimal(str(graph.get(m_id, {}).get(payer_id, 0)))
        if others_owe_payer > 0:
            flow = min(total_to_process, others_owe_payer)
            
            # m_id pays Payer less
            graph[m_id][payer_id] = float(others_owe_payer - flow)
            
            if m_id != receiver_id:
                # m_id now owes that amount to the Receiver instead
                graph[m_id][receiver_id] = float(Decimal(str(graph[m_id].get(receiver_id, 0))) + flow)
            
            total_to_process -= flow

    # STEP 3: Final direct debt
    if total_to_process > 0:
        payer_map[receiver_id] = float(Decimal(str(payer_map.get(receiver_id, 0))) + total_to_process)