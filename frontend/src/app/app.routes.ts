import { Routes } from '@angular/router';

import { HomeComponent } from './home.component';
import { ModelDetailComponent } from './model-detail.component';
import { ModelListComponent } from './model-list.component';
import { ModelTreeComponent } from './model-tree.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: ':modelKey', component: ModelListComponent },
  // The hierarchy tree rooted at this record's topmost ancestor.
  { path: ':modelKey/:pk/tree', component: ModelTreeComponent },
  // pk === 'new' -> create form
  { path: ':modelKey/:pk', component: ModelDetailComponent },
];
