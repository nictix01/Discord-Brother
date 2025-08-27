<?php
// api.php - API Backend pour Discord Dashboard
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST');
header('Access-Control-Allow-Headers: Content-Type');

// Configuration de la base de données (même config que votre bot)
$db_config = [
    'host' => 'localhost',
    'username' => 'root',
    'password' => '',
    'database' => 'discord_dashboard',
    'port' => 3306
];

try {
    $pdo = new PDO(
        "mysql:host={$db_config['host']};port={$db_config['port']};dbname={$db_config['database']};charset=utf8mb4",
        $db_config['username'],
        $db_config['password'],
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false
        ]
    );
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Erreur de connexion à la base de données: ' . $e->getMessage()]);
    exit;
}

// Router simple
$request = $_GET['action'] ?? '';

switch ($request) {
    case 'stats':
        getStats();
        break;
    case 'messages':
        getMessages();
        break;
    case 'users':
        getUsers();
        break;
    case 'servers':
        getServers();
        break;
    case 'channels':
        getChannels();
        break;
    case 'reactions':
        getReactions();
        break;
    case 'recent_activity':
        getRecentActivity();
        break;
    case 'filter_options':
        getFilterOptions();
        break;
    default:
        http_response_code(404);
        echo json_encode(['error' => 'Action non trouvée']);
        break;
}

// Fonction pour obtenir les statistiques générales
function getStats() {
    global $pdo;
    
    try {
        $stats = [];
        
        // Nombre total de messages
        $stmt = $pdo->query("SELECT COUNT(*) as count FROM messages");
        $stats['total_messages'] = $stmt->fetch()['count'];
        
        // Nombre total d'utilisateurs
        $stmt = $pdo->query("SELECT COUNT(*) as count FROM users");
        $stats['total_users'] = $stmt->fetch()['count'];
        
        // Nombre total de serveurs
        $stmt = $pdo->query("SELECT COUNT(*) as count FROM guilds");
        $stats['total_servers'] = $stmt->fetch()['count'];
        
        // Nombre total de salons
        $stmt = $pdo->query("SELECT COUNT(*) as count FROM channels");
        $stats['total_channels'] = $stmt->fetch()['count'];
        
        // Messages par jour (7 derniers jours)
        $stmt = $pdo->query("
            SELECT DATE(created_at) as date, COUNT(*) as count 
            FROM messages 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        ");
        $stats['messages_per_day'] = $stmt->fetchAll();
        
        // Top 5 utilisateurs les plus actifs
        $stmt = $pdo->query("
            SELECT u.username, u.display_name, COUNT(m.message_id) as message_count
            FROM users u
            LEFT JOIN messages m ON u.user_id = m.user_id
            WHERE u.bot = 0
            GROUP BY u.user_id
            ORDER BY message_count DESC
            LIMIT 5
        ");
        $stats['top_users'] = $stmt->fetchAll();
        
        echo json_encode($stats);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des statistiques: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir les messages
function getMessages() {
    global $pdo;
    
    try {
        $limit = $_GET['limit'] ?? 50;
        $offset = $_GET['offset'] ?? 0;
        $guild_id = $_GET['guild_id'] ?? null;
        $channel_id = $_GET['channel_id'] ?? null;
        $user_id = $_GET['user_id'] ?? null;
        $search = $_GET['search'] ?? null;
        
        $where_conditions = [];
        $params = [];
        
        if ($guild_id) {
            $where_conditions[] = "m.guild_id = ?";
            $params[] = $guild_id;
        }
        
        if ($channel_id) {
            $where_conditions[] = "m.channel_id = ?";
            $params[] = $channel_id;
        }
        
        if ($user_id) {
            $where_conditions[] = "m.user_id = ?";
            $params[] = $user_id;
        }
        
        if ($search) {
            $where_conditions[] = "m.content LIKE ?";
            $params[] = "%{$search}%";
        }
        
        $where_clause = !empty($where_conditions) ? "WHERE " . implode(" AND ", $where_conditions) : "";
        
        $sql = "
            SELECT 
                m.message_id,
                m.content,
                m.created_at,
                m.edited_at,
                u.username,
                u.display_name,
                c.channel_name,
                g.guild_name,
                m.attachments,
                m.embeds
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            LEFT JOIN channels c ON m.channel_id = c.channel_id
            LEFT JOIN guilds g ON m.guild_id = g.guild_id
            {$where_clause}
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
        ";
        
        $params[] = (int)$limit;
        $params[] = (int)$offset;
        
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        $messages = $stmt->fetchAll();
        
        // Compter le total pour la pagination
        $count_sql = "
            SELECT COUNT(*) as total
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            LEFT JOIN channels c ON m.channel_id = c.channel_id
            LEFT JOIN guilds g ON m.guild_id = g.guild_id
            {$where_clause}
        ";
        
        $count_params = array_slice($params, 0, -2); // Enlever limit et offset
        $stmt = $pdo->prepare($count_sql);
        $stmt->execute($count_params);
        $total = $stmt->fetch()['total'];
        
        echo json_encode([
            'messages' => $messages,
            'total' => $total,
            'limit' => $limit,
            'offset' => $offset
        ]);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des messages: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir les utilisateurs
function getUsers() {
    global $pdo;
    
    try {
        $limit = $_GET['limit'] ?? 100;
        $offset = $_GET['offset'] ?? 0;
        
        $sql = "
            SELECT 
                u.user_id,
                u.username,
                u.display_name,
                u.discriminator,
                u.bot,
                u.created_at,
                u.first_seen,
                COUNT(m.message_id) as message_count,
                MAX(m.created_at) as last_message
            FROM users u
            LEFT JOIN messages m ON u.user_id = m.user_id
            GROUP BY u.user_id
            ORDER BY message_count DESC
            LIMIT ? OFFSET ?
        ";
        
        $stmt = $pdo->prepare($sql);
        $stmt->execute([(int)$limit, (int)$offset]);
        $users = $stmt->fetchAll();
        
        // Total d'utilisateurs
        $stmt = $pdo->query("SELECT COUNT(*) as total FROM users");
        $total = $stmt->fetch()['total'];
        
        echo json_encode([
            'users' => $users,
            'total' => $total,
            'limit' => $limit,
            'offset' => $offset
        ]);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des utilisateurs: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir les serveurs
function getServers() {
    global $pdo;
    
    try {
        $sql = "
            SELECT 
                g.guild_id,
                g.guild_name,
                g.owner_id,
                g.member_count,
                g.created_at,
                g.joined_at,
                COUNT(DISTINCT c.channel_id) as channel_count,
                COUNT(DISTINCT m.message_id) as message_count
            FROM guilds g
            LEFT JOIN channels c ON g.guild_id = c.guild_id
            LEFT JOIN messages m ON g.guild_id = m.guild_id
            GROUP BY g.guild_id
            ORDER BY g.joined_at DESC
        ";
        
        $stmt = $pdo->query($sql);
        $servers = $stmt->fetchAll();
        
        echo json_encode(['servers' => $servers]);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des serveurs: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir les salons
function getChannels() {
    global $pdo;
    
    try {
        $guild_id = $_GET['guild_id'] ?? null;
        
        $where_clause = $guild_id ? "WHERE c.guild_id = ?" : "";
        $params = $guild_id ? [$guild_id] : [];
        
        $sql = "
            SELECT 
                c.channel_id,
                c.channel_name,
                c.channel_type,
                c.position,
                c.created_at,
                g.guild_name,
                cat.category_name,
                COUNT(m.message_id) as message_count
            FROM channels c
            LEFT JOIN guilds g ON c.guild_id = g.guild_id
            LEFT JOIN categories cat ON c.category_id = cat.category_id
            LEFT JOIN messages m ON c.channel_id = m.channel_id
            {$where_clause}
            GROUP BY c.channel_id
            ORDER BY g.guild_name, c.position
        ";
        
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        $channels = $stmt->fetchAll();
        
        echo json_encode(['channels' => $channels]);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des salons: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir les réactions
function getReactions() {
    global $pdo;
    
    try {
        $limit = $_GET['limit'] ?? 100;
        $offset = $_GET['offset'] ?? 0;
        
        $sql = "
            SELECT 
                r.id,
                r.emoji_name,
                r.emoji_id,
                r.emoji_animated,
                r.created_at,
                u.username,
                u.display_name,
                m.content as message_content,
                c.channel_name,
                g.guild_name
            FROM reactions r
            JOIN users u ON r.user_id = u.user_id
            JOIN messages m ON r.message_id = m.message_id
            LEFT JOIN channels c ON m.channel_id = c.channel_id
            LEFT JOIN guilds g ON m.guild_id = g.guild_id
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        ";
        
        $stmt = $pdo->prepare($sql);
        $stmt->execute([(int)$limit, (int)$offset]);
        $reactions = $stmt->fetchAll();
        
        // Statistiques des emojis les plus utilisés
        $emoji_stats_sql = "
            SELECT 
                emoji_name,
                COUNT(*) as count
            FROM reactions
            GROUP BY emoji_name
            ORDER BY count DESC
            LIMIT 10
        ";
        
        $stmt = $pdo->query($emoji_stats_sql);
        $emoji_stats = $stmt->fetchAll();
        
        // Total des réactions
        $stmt = $pdo->query("SELECT COUNT(*) as total FROM reactions");
        $total = $stmt->fetch()['total'];
        
        echo json_encode([
            'reactions' => $reactions,
            'emoji_stats' => $emoji_stats,
            'total' => $total,
            'limit' => $limit,
            'offset' => $offset
        ]);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des réactions: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir l'activité récente
function getRecentActivity() {
    global $pdo;
    
    try {
        $limit = $_GET['limit'] ?? 20;
        
        $sql = "
            SELECT 
                m.message_id,
                m.content,
                m.created_at,
                'message' as activity_type,
                u.username,
                u.display_name,
                c.channel_name,
                g.guild_name
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            LEFT JOIN channels c ON m.channel_id = c.channel_id
            LEFT JOIN guilds g ON m.guild_id = g.guild_id
            WHERE m.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            
            UNION ALL
            
            SELECT 
                r.id as message_id,
                CONCAT('Réaction ', r.emoji_name, ' ajoutée') as content,
                r.created_at,
                'reaction' as activity_type,
                u.username,
                u.display_name,
                c.channel_name,
                g.guild_name
            FROM reactions r
            JOIN users u ON r.user_id = u.user_id
            JOIN messages m ON r.message_id = m.message_id
            LEFT JOIN channels c ON m.channel_id = c.channel_id
            LEFT JOIN guilds g ON m.guild_id = g.guild_id
            WHERE r.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            
            ORDER BY created_at DESC
            LIMIT ?
        ";
        
        $stmt = $pdo->prepare($sql);
        $stmt->execute([(int)$limit]);
        $activity = $stmt->fetchAll();
        
        echo json_encode(['activity' => $activity]);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération de l\'activité récente: ' . $e->getMessage()]);
    }
}

// Fonction pour obtenir les options de filtres
function getFilterOptions() {
    global $pdo;
    
    try {
        $options = [];
        
        // Serveurs
        $stmt = $pdo->query("SELECT guild_id, guild_name FROM guilds ORDER BY guild_name");
        $options['servers'] = $stmt->fetchAll();
        
        // Salons
        $stmt = $pdo->query("
            SELECT c.channel_id, c.channel_name, g.guild_name 
            FROM channels c 
            JOIN guilds g ON c.guild_id = g.guild_id 
            ORDER BY g.guild_name, c.channel_name
        ");
        $options['channels'] = $stmt->fetchAll();
        
        // Utilisateurs les plus actifs
        $stmt = $pdo->query("
            SELECT u.user_id, u.username, u.display_name, COUNT(m.message_id) as message_count
            FROM users u
            LEFT JOIN messages m ON u.user_id = m.user_id
            WHERE u.bot = 0
            GROUP BY u.user_id
            HAVING message_count > 0
            ORDER BY message_count DESC
            LIMIT 50
        ");
        $options['users'] = $stmt->fetchAll();
        
        echo json_encode($options);
        
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Erreur lors de la récupération des options de filtre: ' . $e->getMessage()]);
    }
}

?>