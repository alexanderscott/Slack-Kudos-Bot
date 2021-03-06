import logging

from chalicelib.global_constants import EMOJI_PLURAL, MAX_POINTS_PER_USER_PER_DAY, BOT_NAME, EMOJI
from chalicelib.persistence_adapter import add_points_to_user, get_user_points, get_number_of_points_given_so_far_today
from chalicelib.slack_api import send_message_to_slack, get_from_slack, GET_USERS, AUTH_TEST, IM_LIST
from chalicelib.slack_message_builder import parse_message

user_mappings = {}
im_list = {}
this_bot = {}


def populate_user_info():
    if not this_bot:
        this_bot['user_id'] = get_from_slack(AUTH_TEST)['user_id']
    if not user_mappings:
        user_info_response = get_from_slack(GET_USERS)
        for user in user_info_response['members']:
            user_mappings[user['id']] = user['profile']['display_name'] or user['profile']['real_name']
    if not im_list:
        im_list_response = get_from_slack(IM_LIST)
        for im in im_list_response['ims']:
            im_list[im['user']] = im['id']


def work_out_points_to_give_and_points_remaining(slack_message):
    so_far_today = get_number_of_points_given_so_far_today(slack_message.sender)
    left_today = max(MAX_POINTS_PER_USER_PER_DAY - so_far_today, 0)

    if slack_message.count_emojis_in_message() <= left_today:
        points_to_give = slack_message.count_emojis_in_message()
    else:
        points_to_give = left_today

    points_remaining = left_today - points_to_give

    return points_to_give, points_remaining


def handle_the_giving_of_emojis(slack_message):

    for recipient in slack_message.recipients:
        points_to_give, points_remaining = work_out_points_to_give_and_points_remaining(slack_message)

        if points_to_give == 0:
            sender_message = f"Sorry, you can't give {user_mappings[recipient]} {EMOJI_PLURAL} because you have you used all your {EMOJI_PLURAL} today already."
            send_message_to_slack(slack_message.sender, sender_message)
        else:
            add_points_to_user(slack_message, recipient, points_to_give)
            sender_message = f'{user_mappings[recipient]} has now been given {points_to_give} {EMOJI_PLURAL}. You have {points_remaining} {EMOJI_PLURAL} left today.'
            send_message_to_slack(im_list.get(slack_message.sender, slack_message.sender), sender_message)

            recipient_message = f'Woohoo! {user_mappings[slack_message.sender]} has given you {points_to_give} {EMOJI_PLURAL}'
            send_message_to_slack(im_list.get(recipient, recipient), recipient_message)


def handle_direct_message(slack_message):
    if EMOJI in slack_message.message:
        response = f"Don't give the {EMOJI} bot {EMOJI_PLURAL}; have some self respect! "
        send_message_to_slack(slack_message.channel, response)
    elif 'leaderboard' in slack_message.message:
        user_totals = get_user_points()

        response = '```\nThe all-time leaderboard is as follows:\n'
        for user, total in user_totals:
            response = response + f'\n{user_mappings[user]}: {total}'
        response = response + '\n```'

        send_message_to_slack(slack_message.channel, response)
    elif 'help' in slack_message.message:
        response = f'To give {EMOJI_PLURAL}:\n```\n@<person> <emoji>\nor\nSome <emoji> <emoji> are due to @<person> for being awesome\n```\n'
        response = response + f'To get the leaderboard:\n```\n@{BOT_NAME} leaderboard\n```'
        send_message_to_slack(slack_message.channel, response)
    else:
        response = f"I didn't understand that command. To see the commands available, type: `@{BOT_NAME} help`"
        send_message_to_slack(slack_message.channel, response)


def deal_with_slack_messages(event):
    slack_message = parse_message(event)
    if slack_message and slack_message.recipients:
        populate_user_info()
        if this_bot['user_id'] in slack_message.recipients:
            handle_direct_message(slack_message)
        elif slack_message.sender in slack_message.recipients and slack_message.count_emojis_in_message():
            send_message_to_slack(slack_message.channel, f"Nice try, but you can't give yourself {EMOJI_PLURAL}")
        elif slack_message.count_emojis_in_message():
            handle_the_giving_of_emojis(slack_message)


def handle_message(data):
    if "challenge" in data:
        return data["challenge"]

    slack_event = data['event']

    if "bot_id" in slack_event:
        logging.warning("Ignore bot event")
    else:
        deal_with_slack_messages(slack_event)