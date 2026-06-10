import { Routes } from '@angular/router';

import { HomeComponent } from './home.component';
import { ModelDetailComponent } from './model-detail.component';
import { ModelListComponent } from './model-list.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: ':modelKey', component: ModelListComponent },
  // pk === 'new' -> create form
  { path: ':modelKey/:pk', component: ModelDetailComponent },
];
