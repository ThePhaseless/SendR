/// <reference types="jasmine" />

import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { ActivatedRoute, type ParamMap, Router, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { AuthComponent } from './auth.component';

function createUserResponse(hasPassword: boolean) {
  return {
    email: 'user@example.com',
    has_password: hasPassword,
    id: 1,
    is_admin: false,
    is_banned: false,
    tier: 'free',
  };
}

class ParamMapStream {
  private readonly subscribers = new Set<(value: ParamMap) => void>();
  value: ParamMap;

  constructor(value: ParamMap) {
    this.value = value;
  }

  readonly observable = {
    subscribe: (observer: ((value: ParamMap) => void) | { next: (value: ParamMap) => void }) => {
      const next = typeof observer === 'function' ? observer : observer.next.bind(observer);
      this.subscribers.add(next);
      next(this.value);
      return {
        unsubscribe: () => {
          this.subscribers.delete(next);
        },
      };
    },
  };

  next(value: ParamMap): void {
    this.value = value;
    for (const subscriber of this.subscribers) {
      subscriber(value);
    }
  }
}

describe('AuthComponent registration password flow', () => {
  let authService: jasmine.SpyObj<AuthService>;
  let router: jasmine.SpyObj<Router>;

  beforeEach(async () => {
    authService = jasmine.createSpyObj<AuthService>(
      'AuthService',
      ['requestCode', 'loginWithPassword', 'setPassword', 'syncSession', 'verifyCode'],
      {
        authenticated: signal(false),
        currentUser: signal(null),
      },
    );
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    router.navigate.and.resolveTo(true);

    authService.requestCode.and.returnValue(of({ message: 'Verification code sent' }));
    authService.verifyCode.and.returnValue(
      of({ expires_at: '2026-05-03T00:00:00Z', token: 'token' }),
    );
    authService.setPassword.and.returnValue(of(createUserResponse(true)));

    await TestBed.configureTestingModule({
      imports: [AuthComponent],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            queryParamMap: of(convertToParamMap({ mode: 'register' })),
            snapshot: {
              queryParamMap: convertToParamMap({ mode: 'register' }),
            },
          },
        },
        {
          provide: AuthService,
          useValue: authService,
        },
        {
          provide: Router,
          useValue: router,
        },
      ],
    }).compileComponents();
  });

  it('renders password fields in register mode', async () => {
    const fixture = TestBed.createComponent(AuthComponent);

    await fixture.whenStable();

    expect(fixture.debugElement.query(By.css('#register-password'))).not.toBeNull();
    expect(fixture.debugElement.query(By.css('#register-password-confirm'))).not.toBeNull();
  });

  it('requires a password before requesting a registration code', () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    component.email = 'user@example.com';
    void component.requestCode();

    expect(authService['requestCode']).not.toHaveBeenCalled();
    expect(component.error()).toBe('Enter a password.');
  });

  it('sets the password after code verification when the account does not have one yet', async () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    authService.currentUser.set(createUserResponse(false));
    component.email = 'user@example.com';
    component.password = 'password123';
    component.confirmPassword = 'password123';
    component.code = '123456';

    await component.verifyCode();
    await fixture.whenStable();

    expect(authService['verifyCode']).toHaveBeenCalledWith('user@example.com', '123456', true);
    expect(authService['syncSession']).toHaveBeenCalledTimes(1);
    expect(authService['setPassword']).toHaveBeenCalledWith('password123');
    expect(router['navigate']).toHaveBeenCalledWith(['/']);
  });

  it('skips password creation when the account already has one', async () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    authService.currentUser.set(createUserResponse(true));
    component.email = 'user@example.com';
    component.password = 'password123';
    component.confirmPassword = 'password123';
    component.code = '123456';

    await component.verifyCode();
    await fixture.whenStable();

    expect(authService['setPassword']).not.toHaveBeenCalled();
    expect(router['navigate']).toHaveBeenCalledWith(['/']);
  });
});

describe('AuthComponent route changes', () => {
  let queryParamMap = new ParamMapStream(convertToParamMap({ mode: 'register' }));

  beforeEach(async () => {
    queryParamMap = new ParamMapStream(convertToParamMap({ mode: 'register' }));

    await TestBed.configureTestingModule({
      imports: [AuthComponent],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            queryParamMap: queryParamMap.observable,
            snapshot: {
              queryParamMap: queryParamMap.value,
            },
          },
        },
        {
          provide: AuthService,
          useValue: {
            authenticated: signal(false),
            currentUser: signal(null),
            loginWithPassword: jasmine.createSpy('loginWithPassword').and.returnValue(of({})),
            requestCode: jasmine
              .createSpy('requestCode')
              .and.returnValue(of({ message: 'Verification code sent' })),
            setPassword: jasmine
              .createSpy('setPassword')
              .and.returnValue(of(createUserResponse(true))),
            syncSession: jasmine.createSpy('syncSession'),
            verifyCode: jasmine.createSpy('verifyCode').and.returnValue(of({})),
          },
        },
        {
          provide: Router,
          useValue: {
            navigate: jasmine.createSpy('navigate'),
          },
        },
      ],
    }).compileComponents();
  });

  it('updates the page mode when query params change on the same route', async () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    await fixture.whenStable();

    expect(component.isRegister()).toBeTrue();
    expect(fixture.nativeElement.textContent).toContain('Create Account');

    component.password = 'password123';
    component.confirmPassword = 'password123';
    component.setMethod('password');
    await fixture.whenStable();

    expect(component.step()).toBe('password');

    queryParamMap.next(convertToParamMap({}));
    await fixture.whenStable();

    expect(component.isRegister()).toBeFalse();
    expect(component.step()).toBe('email');
    expect(component.password).toBe('');
    expect(component.confirmPassword).toBe('');
    expect(fixture.nativeElement.textContent).toContain('Sign In');
  });
});
