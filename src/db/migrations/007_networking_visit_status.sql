-- Add 'networking_visit' contact status for prospects who responded positively
-- but have no current exhibition opportunity — flagged for future networking.
INSERT INTO lookup_values (category, value, label_de, label_en, sort_order)
VALUES ('contact_status', 'networking_visit', 'Netzwerk-Besuch', 'Networking Visit', 15)
ON CONFLICT (category, value) DO NOTHING;
