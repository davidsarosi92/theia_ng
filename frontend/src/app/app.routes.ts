import { Routes } from '@angular/router';

import { AppHomeComponent } from './app-home.component';
import { HomeComponent } from './home.component';
import { LogComponent } from './log.component';
import { ModelDetailComponent } from './model-detail.component';
import { ModelListComponent } from './model-list.component';
import { ModelTreeComponent } from './model-tree.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  // Literal / prefixed routes must precede the :modelKey catch-all.
  { path: 'logs', component: LogComponent },
  { path: 'app/:appLabel', component: AppHomeComponent },
  { path: ':modelKey', component: ModelListComponent },
  // The hierarchy tree rooted at this record's topmost ancestor.
  { path: ':modelKey/:pk/tree', component: ModelTreeComponent },
  // pk === 'new' -> create form
  { path: ':modelKey/:pk', component: ModelDetailComponent },
];
