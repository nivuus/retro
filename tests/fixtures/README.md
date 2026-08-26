# Fixtures

`shortcuts-reel.vdf` a été produit par Steam, pas par ce dépôt. C'est la seule
chose qui atteste la dérivation d'identifiant dans `retro/steam/appid.py` : une
fixture régénérée par notre propre code validerait la formule contre elle-même.

Les chemins qu'il contient ont été neutralisés à la main. Il ne contient aucune
ROM, aucun binaire, aucune donnée personnelle.

Pour en produire une autre : fermer Steam, copier
`userdata/<compte>/config/shortcuts.vdf`, neutraliser les chemins.
