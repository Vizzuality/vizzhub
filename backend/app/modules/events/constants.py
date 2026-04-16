"""Enum constants for the events module."""

from enum import StrEnum


class EventType(StrEnum):
    CONFERENCE = "Conference"
    SUMMIT = "Summit"
    FORUM = "Forum"
    WORKSHOP = "Workshop"
    SYMPOSIUM = "Symposium"
    MULTI_EVENT = "Multi-event"
    NETWORKING_EVENT = "Networking event"
    ROUNDTABLE = "Roundtable"
    TRAINING = "Training"
    WEBINAR = "Webinar"
    EXHIBITION_EXPO = "Exhibition / Expo"
    INTERNAL_EVENT = "Internal event"
    OTHER = "Other"


class Theme(StrEnum):
    CLIMATE = "Climate"
    NATURE_BIODIVERSITY = "Nature & Biodiversity"
    OCEANS_WATER = "Oceans & Water"
    FOOD_LAND_SYSTEMS = "Food & Land Systems"
    ENERGY_NET_ZERO = "Energy & Net Zero"
    DATA_TECHNOLOGY = "Data & Technology"
    POLICY_FINANCE = "Policy & Finance"
    SOCIAL_JUSTICE = "Social Justice"
    URBAN_CITIES = "Urban & Cities"
    OTHER = "Other"


class RegionFocus(StrEnum):
    GLOBAL = "Global"
    EUROPE = "Europe"
    NORTH_AMERICA = "North America"
    LATIN_AMERICA_CARIBBEAN = "Latin America & Caribbean"
    AFRICA = "Africa"
    ASIA_PACIFIC = "Asia-Pacific"
    MIDDLE_EAST = "Middle East"


class AttendeeRole(StrEnum):
    ATTENDEE = "Attendee"
    SPEAKER = "Speaker"
    PANELIST = "Panelist"
    MODERATOR = "Moderator"
    EXHIBITOR = "Exhibitor"
    ORGANIZER = "Organizer"
