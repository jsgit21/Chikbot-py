import os
import requests
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv('WOM_ENDPOINT')
groupid = os.getenv('WOM_GROUPID')
verification_code = os.getenv('WOM_GROUP_VERIFICATION_CODE')
headers = {'user-agent': os.getenv('WOM_USER_AGENT')}

def rank_emoji(rank):
    # Goes off the current assumption that the clan ranks in discord
    # follow the format ccRankTitleCase
    rank = rank.replace('_', ' ')
    rank = rank.title()
    rank = rank.replace(' ', '')
    rank = f'cc{rank}'
    return rank

def clan_ranks(requirement_only=False, titles_only=False):
    total_ranks = {
        'feeder': 0,
        'sapphire': 1000,
        'emerald': 1500,
        'ruby': 1750,
        'diamond': 2000,
        'dragonstone': 2100,
        'onyx': 2200,
        'zenyte': 2300,
        'maxed': 2376,
    }

    # Retired ranks are important to include for the transition
    # period of switching ranks over to a new system
    retired_ranks = {
        'jade': 1000,
        'red_topaz': 1750,
    }


    if titles_only:
        return list(total_ranks.keys()) + list(retired_ranks.keys())

    if requirement_only:
        return total_ranks

    keys = list(total_ranks.keys())

    # Set the ranges for each rank

    # total_ranks = {
    #   'rank1': (0, 999)
    #   'rank2': (1000, ...)
    #}

    for index, (rank, total_req) in enumerate(total_ranks.items()):
        # maxed rank does not have a total range
        if rank == 'maxed':
            total_ranks[rank] = (total_req, total_req)
            break

        next_rank = keys[index+1]
        next_rank_req = total_ranks[next_rank]
        rank_range = (total_req, next_rank_req-1)
        total_ranks[rank] = rank_range

    return total_ranks

def determine_rank(user_total):
    ranks = clan_ranks()

    for rank, (req, limit) in ranks.items():
        if req <= user_total <= limit:
            return rank
    return None

def append_determined_ranks(group):
    for user_id, user in group.items():
        # For users that are not on the hiscores, default -1
        user_total = user.get('total', -1)
        user['determined_rank'] = determine_rank(user_total)

def append_rank_discord_emojis(group):
    for user_id, user in group.items():
        if user.get('total') is not None:
            user['current_rank_emoji'] = rank_emoji(user['current_rank'])
            user['determined_rank_emoji'] = rank_emoji(user['determined_rank'])

def append_total_levels(group):
    hiscores_endpoint = f'/{groupid}/hiscores?metric=overall&limit=10000'
    url = endpoint + hiscores_endpoint
    response = requests.get(url, headers)
    player_data = response.json()

    for player_obj in player_data:
        player = player_obj['player']
        data = player_obj['data']
        id = player['id']
        player_dict = group[id]

        player_dict['total'] = data['level']
        #player_dict['lastChangedAt'] = player['lastChangedAt']

def get_user_roles(rank=None):
    group_details_endpoint = f'/{groupid}'
    url = endpoint + group_details_endpoint
    response = requests.get(url, headers)

    group_details = response.json()
    memberships = group_details['memberships']
    parsed_data = {}

    for player_obj in memberships:
        player = player_obj['player']
        id = player['id']
        player_dict = {}

        player_dict['username'] = player['username']
        player_dict['current_rank'] = player_obj['role']
        parsed_data[id] = player_dict

    if rank:
        users_with_rank = {}
        for user_id, user in parsed_data.items():
            if user['current_rank'] == rank:
                users_with_rank[user_id] = user
        return users_with_rank

    return parsed_data

def bulk_update_outdated_users():
    update_endpoint = f'/{groupid}/update-all'
    json_data = {'verificationCode': verification_code}
    url = endpoint + update_endpoint

    response = requests.post(url, headers=headers, json=json_data)

    return response.json()['message']

def get_misranked_users():
    # Returns a list of users who need rank updates
    # As long as their current rank is one of the total level ranks
    # Which means it will ignore any specialty ranks

    group_details = get_user_roles()
    append_total_levels(group_details)
    append_determined_ranks(group_details)
    append_rank_discord_emojis(group_details)

    misranked_users = []

    rank_titles = clan_ranks(titles_only=True)
    for user, data in group_details.items():
        unmatched_rank = data['current_rank'] != data['determined_rank']
        valid_role = data['current_rank'] in rank_titles
        has_determined_rank = data['determined_rank'] is not None
        if unmatched_rank and valid_role and has_determined_rank:
            misranked_users.append(data)

    return misranked_users

def get_members_with_ranks():
    all_members = get_user_roles()
    all_members = [
        [user_id, member['username'], member['current_rank']]
        for user_id, member in all_members.items()
    ]
    return all_members


if __name__ == '__main__':
    for user, values in get_user_roles().items():
        print(values['username'])


