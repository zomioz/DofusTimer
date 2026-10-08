# Dofus Timer

Petit outil Windows qui additionne les durées de combat affichées par le popup de fin de combat de Dofus.

Il fonctionne uniquement par capture d'écran et OCR : il n'envoie aucune touche ni aucun clic, et ne touche pas au processus du jeu.

## Installation (Windows 11)

1. Onglet **Releases** du dépôt GitHub : télécharge `DofusTimer-windows.zip`.
2. Extrais le zip, puis lance `DofusTimer.exe`.
3. Si SmartScreen affiche « Windows a protégé votre PC » : **Informations complémentaires**, puis **Exécuter quand même** (l'exécutable n'est pas signé).

Prérequis : une langue Windows avec OCR (le français ou l'anglais installés par défaut suffisent).

## Utilisation

1. Dofus en mode **fenêtré** ou **plein écran sans bordure**.
2. Premier lancement : termine un combat, laisse le popup affiché, clique sur **Calibrer** et entoure (1) un élément fixe du popup, puis (2) la durée. Le résultat de lecture est affiché pour vérification. La calibration est mémorisée dans `%APPDATA%\DofusTimer`.
3. **Départ** remet le total à zéro et lance la surveillance, **Stop** l'arrête. Recalibre si tu changes la résolution ou l'échelle de l'interface.

Si un popup n'est pas lu, la zone est sauvegardée dans `%APPDATA%\DofusTimer\last_failed.png`.

## Écran noir à la calibration

Dofus est alors en plein écran exclusif : passe-le en mode fenêtré ou sans bordure. Un mode sans bordure se reconnaît à un Alt+Tab instantané, sans clignotement ni changement de résolution.

## Développement

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pytest
python -m pytest
python main.py
```

L'exécutable est construit par GitHub Actions à chaque tag `vX.Y.Z` (`git tag v0.1.0 && git push origin v0.1.0`).
