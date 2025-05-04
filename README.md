Guide d'installation simplifié pour l'application de gestion des ventes sur Back4app
Ce guide vous explique comment déployer et lancer l'application sur la plateforme Back4app Containers en utilisant Docker.
Prérequis :
Avoir un compte GitHub (ou GitLab/Bitbucket) pour héberger le code source.
Avoir un compte Back4app (un compte gratuit peut suffire pour commencer : https://www.back4app.com/ ).
Avoir vos clés API prêtes :
Votre Jeton d'accès personnel Airtable (PAT)
L'ID de votre base Airtable
Votre clé API ImgBB
Étapes :
Préparer votre dépôt Git (GitHub) :
Créez un nouveau dépôt (privé ou public) sur GitHub.
Transférez le contenu du dossier src de l'archive book_sales_manager_docker.zip (c'est-à-dire les fichiers main.py, requirements.txt, Dockerfile et le dossier static avec index.html et logo famille.jpeg) à la racine de ce nouveau dépôt GitHub.
Important : Assurez-vous que le fichier Dockerfile est bien à la racine du dépôt.
Créer une Application Conteneur sur Back4app :
Connectez-vous à votre tableau de bord Back4app.
Allez dans la section "Containers" et cliquez sur "New Container App".
Choisissez "Import from a Git Repository".
Connectez votre compte GitHub à Back4app si ce n'est pas déjà fait.
Sélectionnez le dépôt GitHub que vous venez de créer à l'étape 1.
Configurez les informations de base de l'application (nom, région, branche Git - généralement main ou master).
Configurer les Variables d'Environnement :
Dans les paramètres de votre application conteneur sur Back4app, trouvez la section "Environment Variables".
Ajoutez les variables suivantes en remplaçant les valeurs par vos propres clés :
AIRTABLE_API_KEY = VOTRE_JETON_AIRTABLE_ICI
AIRTABLE_BASE_ID = VOTRE_ID_BASE_AIRTABLE_ICI
AIRTABLE_TABLE_NAME = ventes caisse (Vérifiez que le nom est exact)
IMGBB_API_KEY = VOTRE_CLE_IMGBB_ICI
FLASK_RUN_PORT = 5001 (Le port exposé dans le Dockerfile)
PORT = 5001 (Back4app utilise souvent cette variable pour savoir quel port écouter)
Note : Le fichier docker-compose.yml n'est pas utilisé directement par Back4app dans ce mode de déploiement ; les variables d'environnement sont gérées via l'interface.
Configurer le Port :
Dans les paramètres de l'application Back4app, assurez-vous que le port exposé est bien 5001 (correspondant à FLASK_RUN_PORT et PORT).
Lancer le Déploiement :
Sauvegardez la configuration.
Back4app va automatiquement récupérer le code depuis GitHub, construire l'image Docker en utilisant le Dockerfile, et déployer l'application.
Vous pourrez suivre l'avancement dans les logs de déploiement sur Back4app.
Accéder à l'application :
Une fois le déploiement réussi, Back4app vous fournira une URL publique (généralement sous la forme VOTRE-APP-NOM.b4a.run).
Ouvrez cette URL dans votre navigateur web.
Votre application devrait maintenant être accessible via l'URL fournie par Back4app !
Mises à jour :
Pour mettre à jour l'application, il suffit de pousser les modifications du code (par exemple, si on modifie index.html ou main.py) sur votre dépôt GitHub. Back4app détectera les changements et redéploiera automatiquement (selon votre configuration).
Limitations possibles (Niveau Gratuit) :
L'application peut se mettre en veille après une période d'inactivité (le premier accès après la veille sera plus long).
Les ressources (CPU/RAM) sont limitées.
L'URL est fournie par Back4app ; un nom de domaine personnalisé nécessite généralement un plan payant.
