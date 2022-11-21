from __future__ import annotations

from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Union

import valorantx

if TYPE_CHECKING:
    from typing_extensions import Self


class AgentEmoji(str, Enum):

    astra = '<:agent_astra:1042813586835243050>'
    breach = '<:agent_breach:1042813549484970054>'
    brimstone = '<:agent_brimstone:1042813590354264064>'
    chamber = '<:agent_chamber:1042813558309789716>'
    cypher = '<:agent_cypher:1042813567835050084>'
    fade = '<:agent_fade:1042813612131111063>'
    harbor = '<:agent_harbor:1042813576370454568>'
    jett = '<:agent_jett:1042813609312538814>'
    kay_o = '<:agent_kay_o:1042813561052876902>'
    killjoy = '<:agent_killjoy:1042813573799366686>'
    neon = '<:agent_neon:1042813593722294363>'
    omen = '<:agent_omen:1042813606363938916>'
    phoenix = '<:agent_phoenix:1042813583693721712>'
    raze = '<:agent_raze:1042813552681037855>'
    reyna = '<:agent_reyna:1042813602354176020>'
    sage = '<:agent_sage:1042813598822563892>'
    skye = '<:agent_skye:1042813564521549914>'
    sova = '<:agent_sova:1042813570846576660>'
    viper = '<:agent_viper:1042813580409585704>'
    yoru = '<:agent_yoru:1042813595710410833>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def get(cls, agent: Union[valorantx.Agent, str]) -> str:
        display_name = agent.display_name if isinstance(agent, valorantx.Agent) else agent
        return cls.__members__.get(display_name.lower().replace("/", "_").replace(" ", "_"), '')


class AbilitiesEmoji(str, Enum):
    astra_astral_form = "<:astra_astral_form:1042933622438641725>"
    astra_astral_form_cosmic_divide = "<:astra_astral_form_cosmic_divide:1042933624451895426>"
    astra_gravity_well = "<:astra_gravity_well:1042933620563775538>"
    astra_nebula_dissipate = "<:astra_nebula_dissipate:1042933618663759912>"
    astra_nova_pulse = "<:astra_nova_pulse:1042933616625340427>"
    breach_aftershock = "<:breach_aftershock:1042933331190370344>"
    breach_fault_line = "<:breach_fault_line:1042933329231618108>"
    breach_flashpoint = "<:breach_flashpoint:1042933327113486377>"
    breach_rolling_thunder = "<:breach_rolling_thunder:1042933333266546688>"
    brimstone_incendiary = "<:brimstone_incendiary:1042933509225984020>"
    brimstone_orbital_strike = "<:brimstone_orbital_strike:1042933514896678923>"
    brimstone_sky_smoke = "<:brimstone_sky_smoke:1042933511079854200>"
    brimstone_stim_beacon = "<:brimstone_stim_beacon:1042933513252507680>"
    chamber_headhunter = "<:chamber_headhunter:1042934136484155494>"
    chamber_rendezvous = "<:chamber_rendezvous:1042934138774245496>"
    chamber_tour_de_force = "<:chamber_tour_de_force:1042934142716883014>"
    chamber_trademark = "<:chamber_trademark:1042934140816871454>"
    cypher_cyber_cage = "<:cypher_cyber_cage:1042933746397089872>"
    cypher_neural_theft = "<:cypher_neural_theft:1042933752206204938>"
    cypher_spycam = "<:cypher_spycam:1042933748246782052>"
    cypher_trapwire = "<:cypher_trapwire:1042933750167773205>"
    fade_haunt = "<:fade_haunt:1042934633538519100>"
    fade_nightfall = "<:fade_nightfall:1042934638198394880>"
    fade_prowler = "<:fade_prowler:1042934636193517628>"
    fade_seize = "<:fade_seize:1042934631034531850>"
    harbor_cascade = "<:harbor_cascade:1042933682878558218>"
    harbor_cove = "<:harbor_cove:1042933675156844624>"
    harbor_high_tide = "<:harbor_high_tide:1042933679321784460>"
    harbor_reckoning = "<:harbor_reckoning:1042933685336416349>"
    jett_blade_storm = "<:jett_blade_storm:1042934484154196113>"
    jett_cloudburst = "<:jett_cloudburst:1042934480308023366>"
    jett_drift = "<:jett_drift:1042934482405171261>"
    jett_tailwind = "<:jett_tailwind:1042934478508671016>"
    jett_updraft = "<:jett_updraft:1042934476696731719>"
    kay_o_flash_drive = "<:kay_o_flash_drive:1042933938101952533>"
    kay_o_frag_ment = "<:kay_o_frag_ment:1042933942141071441>"
    kay_o_null_cmd = "<:kay_o_null_cmd:1042933944787681370>"
    kay_o_zero_point = "<:kay_o_zero_point:1042933940383662150>"
    killjoy_alarmbot = "<:killjoy_alarmbot:1042933288278433945>"
    killjoy_lockdown = "<:killjoy_lockdown:1042933294439870554>"
    killjoy_nanoswarm = "<:killjoy_nanoswarm:1042933292502110380>"
    killjoy_turret = "<:killjoy_turret:1042933290337828954>"
    neon_fast_lane = "<:neon_fast_lane:1042934594263060491>"
    neon_high_gear = "<:neon_high_gear:1042934589619978250>"
    neon_overdrive = "<:neon_overdrive:1042934596112764969>"
    neon_relay_bolt = "<:neon_relay_bolt:1042934587199852555>"
    omen_dark_cover = "<:omen_dark_cover:1042933474388103209>"
    omen_from_the_shadows = "<:omen_from_the_shadows:1042933478582407298>"
    omen_paranoia = "<:omen_paranoia:1042933472504852590>"
    omen_shrouded_step = "<:omen_shrouded_step:1042933476527190026>"
    phoenix_blaze = "<:phoenix_blaze:1042934798613757983>"
    phoenix_curveball = "<:phoenix_curveball:1042934794033565796>"
    phoenix_hot_hands = "<:phoenix_hot_hands:1042934795946176573>"
    phoenix_run_it_back = "<:phoenix_run_it_back:1042934800861900840>"
    raze_blast_pack = "<:raze_blast_pack:1042934830742110228>"
    raze_boom_bot = "<:raze_boom_bot:1042934834886103100>"
    raze_paint_shells = "<:raze_paint_shells:1042934832684093500>"
    raze_showstopper = "<:raze_showstopper:1042934836794507357>"
    reyna_devour = "<:reyna_devour:1042934215278338058>"
    reyna_dismiss = "<:reyna_dismiss:1042934229182447707>"
    reyna_empress = "<:reyna_empress:1042934257225580544>"
    reyna_leer = "<:reyna_leer:1042934243132723200>"
    sage_barrier_orb = "<:sage_barrier_orb:1042933877372637214>"
    sage_healing_orb = "<:sage_healing_orb:1042933875267088424>"
    sage_resurrection = "<:sage_resurrection:1042933879440408606>"
    sage_slow_orb = "<:sage_slow_orb:1042933873232846868>"
    skye_guiding_light = "<:skye_guiding_light:1042933381102567465>"
    skye_regrowth = "<:skye_regrowth:1042933383128420352>"
    skye_seekers = "<:skye_seekers:1042933385208807445>"
    skye_trailblazer = "<:skye_trailblazer:1042933378833449002>"
    sova_hunters_fury = "<:sova_hunters_fury:1042933804500795392>"
    sova_owl_drone = "<:sova_owl_drone:1042933802315546654>"
    sova_recon_bolt = "<:sova_recon_bolt:1042933800428122152>"
    sova_shock_bolt = "<:sova_shock_bolt:1042933798297419826>"
    viper_poison_cloud = "<:viper_poison_cloud:1042934084529307658>"
    viper_snake_bite = "<:viper_snake_bite:1042934088497119252>"
    viper_toxic_screen = "<:viper_toxic_screen:1042934086660005999>"
    viper_vipers_pit = "<:viper_vipers_pit:1042934090673954866>"
    yoru_blindside = "<:yoru_blindside:1042933413042196570>"
    yoru_dimensional_drift = "<:yoru_dimensional_drift:1042933418700308521>"
    yoru_fakeout = "<:yoru_fakeout:1042933416863219742>"
    yoru_gatecrash = "<:yoru_gatecrash:1042933414841565205>"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def get(cls, name: str) -> str:
        return cls.__members__.get(name, '')


class GameModeEmoji(str, Enum):
    standard = '<:gamemode_standard:1042834174664527902>'
    unrated = '<:gamemode_standard:1042834174664527902>'
    competitive = '<:gamemode_standard:1042834174664527902>'
    spike_rush = '<:gamemode_spike_rush:1042834185179635763>'
    deathmatch = '<:gamemode_deathmatch:1042834182822441030>'
    escalation = '<:gamemode_escalation:1042834180691738655>'
    replication = '<:gamemode_replication:1042834178535862282>'
    snowball_fight = '<:gamemode_snowball_fight:1042834176606486558>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def get(cls, name: str) -> str:
        name = name.replace(' ', '_')
        return cls.__members__.get(name.lower(), '')


class ContentTierEmoji(str, Enum):

    deluxe = '<:content_tier_deluxe:1042810257426108557>'
    exclusive = '<:content_tier_exclusive:1042810259317735434>'
    premium = '<:content_tier_premium:1042810261289050224>'
    select = '<:content_tier_select:1042810263361036360>'
    ultra = '<:content_tier_ultra:1042810265906991104>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def get(cls, content_tier: Union[valorantx.ContentTier, str]) -> str:
        name = content_tier.dev_name if isinstance(content_tier, valorantx.ContentTier) else content_tier
        return cls.__members__.get(name, '')


class RoundResultEmoji(str, Enum):
    diffuse_loss = '<:diffuse_loss:1042809400592715816>'
    diffuse_win = '<:diffuse_win:1042809402526281778>'
    elimination_loss = '<:elimination_loss:1042809418661761105>'
    elimination_win = '<:elimination_win:1042809420549206026>'
    explosion_loss = '<:explosion_loss:1042809464274812988>'
    explosion_win = '<:explosion_win:1042809466137083996>'
    time_loss = '<:time_loss:1042809483270832138>'
    time_win = '<:time_win:1042809485128896582>'
    surrendered = '<:EarlySurrender_Flag:1042829113741819996>'

    def __str__(self) -> str:
        return str(self.value)


class TierEmoji(str, Enum):

    radiant = '<:tier_radiant:1043967005956509760>'
    immortal_3 = '<:tier_immortal_3:1043966994665443398>'
    immortal_2 = '<:tier_immortal_2:1043966983068209243>'
    immortal_1 = '<:tier_immortal_1:1043966961782112316>'
    immortal = '<:tier_immortal_3:1043966994665443398>'
    ascendant_3 = '<:tier_ascendant_3:1043966927468503111>'
    ascendant_2 = '<:tier_ascendant_2:1043966916865310751>'
    ascendant_1 = '<:tier_ascendant_1:1043966907180646521>'
    diamond_3 = '<:tier_diamond_3:1043966895201718453>'
    diamond_2 = '<:tier_diamond_2:1043966882518151260>'
    diamond_1 = '<:tier_diamond_1:1043966868756635708>'
    platinum_3 = '<:tier_platinum_3:1043966856983228418>'
    platinum_2 = '<:tier_platinum_2:1043966847139196999>'
    platinum_1 = '<:tier_platinum_1:1043966836498235452>'
    gold_3 = '<:tier_gold_3:1043966825815355443>'
    gold_2 = '<:tier_gold_2:1043966814301999205>'
    gold_1 = '<:tier_gold_1:1043966803023511602>'
    silver_3 = '<:tier_silver_3:1043966751643275324>'
    silver_2 = '<:tier_silver_2:1043966739773411338>'
    silver_1 = '<:tier_silver_1:1043966727081427105>'
    bronze_3 = '<:tier_bronze_3:1043966716222394428>'
    bronze_2 = '<:tier_bronze_2:1043966705875034182>'
    bronze_1 = '<:tier_bronze_1:1043966695527694497>'
    iron_3 = '<:tier_iron_3:1043966681032183908>'
    iron_2 = '<:tier_iron_2:1043966668298260550>'
    iron_1 = '<:tier_iron_1:1043966655753113680>'
    unranked = '<:tier_unranked:1043966640674574366>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def get(cls, tier: Union[valorantx.Tier, str]) -> str:
        name = tier.display_name if isinstance(tier, valorantx.Tier) else tier
        return cls.__members__.get(name.replace(' ', '_').lower(), '')


class PointEmoji(Enum):

    valorant = '<:currency_valorant:1042817047953952849>'
    radianite = '<:currency_radianite:1042817896398737417>'
    free_agent = '<:currency_free_agents:1042817043965165580>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def get(cls, name: str) -> str:
        return cls.__members__.get(name, '')


class ResultColor(IntEnum):
    win = 0x60DCC4
    lose = 0xFC5C5C
    draw = 0xCBCCD6


class ValorantLocale(Enum):
    en_US = 'en-US'
    en_GB = 'en-US'
    zh_CN = 'zh-CN'
    zh_TW = 'zh-TW'
    fr = 'fr-FR'
    de = 'de-DE'
    it = 'it-IT'
    ja = 'ja-JP'
    ko = 'ko-KR'
    pl = 'pl-PL'
    pt_BR = 'pt-BR'
    ru = 'ru-RU'
    es_ES = 'es-ES'
    th = 'th-TH'
    tr = 'tr-TR'
    vi = 'vi-VN'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_discord(cls, value: str) -> Self:
        value = value.replace('-', '_')
        locale = getattr(cls, value, None)
        if locale is None:
            raise ValueError(f'Invalid locale: {value}')
        return locale
