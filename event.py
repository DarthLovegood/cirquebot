import re
from json import dumps, loads

FACTION_UNDEFINED = ''
FACTION_PUB = 'Republic'
FACTION_IMP = 'Empire'

REGEX_PUB = re.compile('^(re)?pube*(lic)? *(side)?$')
REGEX_IMP = re.compile('^s*[ei]mp(ire)?(erial)? *(side)?$')

TANK_ROLE_STR = 'Tanks'
HEALER_ROLE_STR = 'Healers'
DPS_ROLE_STR = 'DPS'

SUB_TANK_ROLE_STR = 'Sub Tanks'
SUB_HEALER_ROLE_STR = 'Sub Healers'
SUB_DPS_ROLE_STR = 'Sub DPS'


class Event:

    def __init__(self):
        self.title = ''
        self.faction = FACTION_UNDEFINED

        # TODO: Is this necessary?
        # self.signups_open = False

        self.date = ''
        self.time = ''
        self.calendar_url = ''

        self.reqs = {TANK_ROLE_STR: '', HEALER_ROLE_STR: '', DPS_ROLE_STR: ''}
        self.capacity = {TANK_ROLE_STR: 2, HEALER_ROLE_STR: 2, DPS_ROLE_STR: 4}
        self.players = {TANK_ROLE_STR: [], HEALER_ROLE_STR: [], DPS_ROLE_STR: [],
                        SUB_TANK_ROLE_STR: [], SUB_HEALER_ROLE_STR: [], SUB_DPS_ROLE_STR: []}

    def to_dict(self):
        return vars(self)

    @staticmethod
    def from_dict(event_dict):
        event = Event()
        for key in event_dict:
            setattr(event, key, event_dict[key])
        return event

    def to_json(self):
        return dumps(self.to_dict(), indent=2)

    # Returns an Event if the json is valid, and an error message string otherwise.
    @staticmethod
    def from_json(ctx, event_json):
        event = Event.from_dict(loads(event_json))

        faction_str = event.faction.lower()
        if re.fullmatch(REGEX_PUB, faction_str):
            event.faction = FACTION_PUB
        elif re.fullmatch(REGEX_IMP, faction_str):
            event.faction = FACTION_IMP
        else:
            event.faction = FACTION_UNDEFINED

        for value in event.capacity.values():
            if not isinstance(value, int):
                return 'Capacity values must be integers.'

        for role, player_list in event.players.items():
            user_id_list = []
            for player_name in player_list:
                member = (ctx.bot.get_cog('Nicknames').get_member_by_nickname(ctx, player_name)
                          or ctx.guild.get_member_named(player_name))
                if member:
                    user_id_list.append(member.id)
                else:
                    return f'Could not find player named **{player_name}**.'
            event.players[role] = user_id_list

        return event

    def to_string(self, use_player_ids=True):
        if use_player_ids:
            # TODO: Implement!
            pass
        return str(self.to_dict())

    def from_string(self):
        # TODO: Implement!
        pass
