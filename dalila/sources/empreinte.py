"""Empreinte d'un contenu : détecte qu'une source a changé sans garder ni comparer tout le texte.

    empreinte_texte("Zone  industrielle\n de Sfax")  == empreinte_texte("Zone industrielle de Sfax")   # True
    empreinte_octets(pdf)                                                                             # PDF : octets bruts

Le texte est normalisé avant le calcul (Unicode NFC, espaces et retours à la ligne fusionnés) : une page dont seule la
mise en forme change garde la même empreinte. Les menus, en-têtes et pieds de page sont déjà retirés par lire.py.
"""
import hashlib, re, unicodedata


def normaliser(texte):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", texte or "")).strip()


def empreinte_texte(texte):
    return hashlib.sha256(normaliser(texte).encode("utf-8")).hexdigest()


def empreinte_octets(octets):
    return hashlib.sha256(octets or b"").hexdigest()
