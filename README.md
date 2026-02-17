# 📦 PRO-STOCK : Gestionnaire d'Inventaire Studio

**ProStock** est une application de gestion d'inventaire développée en Python (PyQt6) pour les studios de production et les prestataires techniques. Elle permet de suivre le matériel audiovisuel (Son, Lumière, Vidéo, Câblage) avec une gestion précise des entrées/sorties via QR Codes.

![Status](https://img.shields.io/badge/Status-Stable-green)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## ✨ Fonctionnalités Principales

* **📊 Inventaire Temps Réel** : Suivi des quantités, numéros de série (S/N) et valeur du parc.
* **🔌 Gestion Intelligente des Câbles** : Bibliothèque de connecteurs (XLR, Jack, HDMI...) et gestion par lots/longueurs.
* **📱 QR Codes & Scan** : Génération automatique de QR Codes uniques, impression de planches PDF et scan via Webcam ou douchette USB.
* **🔄 Check In / Check Out** : Suivi des sorties matériel avec horodatage pour savoir qui a quoi et depuis quand.
* **🛠️ Module Maintenance** : Gestion du cycle de vie (Stock -> En Panne -> Réparateur -> Stock) et suivi des coûts de réparation.
* **🧰 Gestion des Kits** : Création de lots virtuels (ex: "Kit Interview") pour sortir plusieurs objets en un clic.
* **📈 Dashboard** : Indicateurs financiers, taux d'occupation et alertes maintenance.
* **📄 Exports** : Exportation des données en CSV (Excel) et planches d'étiquettes en PDF.

## 🛠️ Installation

### Prérequis
* Python 3.x
* Pip

### Installation Rapide

1.  **Cloner le dépôt**
    ```bash
    git clone [https://github.com/VOTRE_NOM_UTILISATEUR/InventaireMatos.git](https://github.com/VOTRE_NOM_UTILISATEUR/InventaireMatos.git)
    cd InventaireMatos
    ```

2.  **Créer un environnement virtuel (Recommandé)**
    ```bash
    python -m venv venv
    # Sur Windows :
    .\venv\Scripts\activate
    # Sur Mac/Linux :
    source venv/bin/activate
    ```

3.  **Installer les dépendances**
    ```bash
    pip install PyQt6 opencv-python pyzbar qrcode reportlab
    ```
    *(Note : Si vous avez des soucis avec zbar sur Windows, installez l'exécutable Visual C++ redistributable)*

4.  **Lancer l'application**
    ```bash
    python main.py
    ```

## 📂 Structure du Projet

* `main.py` : Cœur de l'application (Interface & Logique).
* `database.py` : Gestion de la base de données SQLite (`inventaire.db`).
* `styles.qss` : Feuille de style pour le Dark Mode (Thème pro).
* `data/` :
    * `qrcodes/` : Stockage des images QR générées.
    * `factures/` : Stockage des PDF/Images de factures.

## 🚀 Utilisation

1.  **Ajouter du matériel** : Cliquez sur `+ Ajouter`. Pour les câbles, sélectionnez la catégorie "Câblage" pour activer le générateur de noms automatique.
2.  **Imprimer les étiquettes** : Sélectionnez vos lignes et cliquez sur `🖨️ QR` pour générer un PDF A4 prêt à imprimer.
3.  **Sortir du matériel** : Scannez le QR code avec une douchette ou cliquez sur "Sortir".
4.  **Maintenance** : Si un objet est cassé, cliquez sur `🛠️` (Maintenance). Il sera bloqué en sortie jusqu'à sa réparation.

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour des changements majeurs, veuillez ouvrir une issue d'abord pour discuter de ce que vous aimeriez changer.

## 📝 Auteur

Développé pour la gestion de studio pro.