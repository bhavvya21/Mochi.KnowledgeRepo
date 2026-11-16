CREATE TABLE `documents` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`name` text NOT NULL,
	`type` text NOT NULL,
	`collection` text NOT NULL,
	`object_key` text NOT NULL,
	`size` integer NOT NULL,
	`chars` integer NOT NULL,
	`pages` integer NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `documents_owner_created` ON `documents` (`owner`,`created`);