import {sqliteTable,text,integer,index} from 'drizzle-orm/sqlite-core';
export const documents=sqliteTable('documents',{
 id:text('id').primaryKey(),owner:text('owner').notNull(),name:text('name').notNull(),type:text('type').notNull(),collection:text('collection').notNull(),objectKey:text('object_key').notNull(),size:integer('size').notNull(),chars:integer('chars').notNull(),pages:integer('pages').notNull(),created:text('created').notNull()
},t=>[index('documents_owner_created').on(t.owner,t.created)]);
export const browserSessions=sqliteTable('browser_sessions',{
 tokenHash:text('token_hash').primaryKey(),owner:text('owner').notNull(),expires:integer('expires').notNull()
});
