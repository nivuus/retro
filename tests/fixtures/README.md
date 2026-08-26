# Fixtures

`shortcuts-reel.vdf` a été produit par Steam, pas par ce dépôt. C'est la seule
chose qui atteste la dérivation d'identifiant dans `retro/steam/appid.py` : une
fixture régénérée par notre propre code validerait la formule contre elle-même.

Seuls les `appid` et la forme du fichier viennent de l'installation d'origine.
Tout le reste a été réécrit : les titres sont des inventions choisies pour
couvrir l'Unicode que Steam doit survivre (accents, apostrophe typographique
U+2019, deux-points, parenthèses), et les chemins, les tags et les noms de
lanceurs sont génériques. Le fichier ne contient ni ROM, ni binaire, ni titre
réel, ni nom de produit, ni chemin personnel, ni identifiant de compte.

Pour en produire une autre : fermer Steam, copier
`userdata/<compte>/config/shortcuts.vdf`, puis réécrire titres, chemins et tags
via la bibliothèque `vdf` en laissant les `appid` intacts — ce sont eux, et eux
seuls, que les tests lisent.
