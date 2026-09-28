using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace frontend.Common;

// ====================== STATUS CODE ENUM ======================
[JsonConverter(typeof(JsonStringEnumConverter))]
public enum CRUDStatusCodeRes
{
    // Success
    SUCCESS = 200,
    CREATED = 201,
    NO_DATA = 204,

    // Client errors
    BAD_REQUEST = 400,
    UNAUTHORIZED = 401,
    PAYMENT_REQUIRED = 402,
    FORBIDDEN = 403,
    NOT_FOUND = 404,
    CONFLICT = 409,
    UNPROCESSABLE_ENTITY = 422,

    TOO_MANY_REQUESTS = 429,
    // Server errors
    INTERNAL_SERVER_ERROR = 500
}

// ====================== API RESULT ======================
public sealed class ApiResult<T>
{
    [JsonPropertyName("code")]
    public CRUDStatusCodeRes Code { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;

    [JsonPropertyName("is_success")]
    public bool IsSuccess { get; set; }

    [JsonPropertyName("data")]
    public T? Data { get; set; }

    [JsonPropertyName("errors")]
    public Dictionary<string, List<string>>? Errors { get; set; }

    public ApiResult() { }

    [JsonConstructor]
    private ApiResult(
        CRUDStatusCodeRes code,
        bool isSuccess,
        string message,
        T? data = default,
        Dictionary<string, List<string>>? errors = null)
    {
        Code = code;
        IsSuccess = isSuccess;
        Message = message;
        Data = data;
        Errors = errors;
    }

    // ====================== Success ======================

    public static ApiResult<T> Success(T? data = default, string message = "Success")
        => new(CRUDStatusCodeRes.SUCCESS, true, message, data);

    public static ApiResult<T> Created(T? data = default, string message = "Created")
        => new(CRUDStatusCodeRes.CREATED, true, message, data);

    public static ApiResult<T> NoData(string message = "No data")
        => new(CRUDStatusCodeRes.SUCCESS, true, message);

    public static ApiResult<T> Deleted(string message = "Deleted successfully")
        => new(CRUDStatusCodeRes.SUCCESS, true, message);

    // ====================== Error ======================

    public static ApiResult<T> Error(
        string message = "An error occurred",
        CRUDStatusCodeRes code = CRUDStatusCodeRes.INTERNAL_SERVER_ERROR)
        => new(code, false, message);

    public static ApiResult<T> BadRequest(string message = "Bad request")
        => Error(message, CRUDStatusCodeRes.BAD_REQUEST);

    public static ApiResult<T> Unauthorized(string message = "Unauthorized")
        => Error(message, CRUDStatusCodeRes.UNAUTHORIZED);

    public static ApiResult<T> Forbidden(string message = "Forbidden")
        => Error(message, CRUDStatusCodeRes.FORBIDDEN);

    public static ApiResult<T> NotFound(string message = "Not found")
        => Error(message, CRUDStatusCodeRes.NOT_FOUND);

    public static ApiResult<T> Conflict(string message = "Conflict")
        => Error(message, CRUDStatusCodeRes.CONFLICT);

    public static ApiResult<T> InternalServerError(string message = "Internal server error")
        => Error(message, CRUDStatusCodeRes.INTERNAL_SERVER_ERROR);

    public static ApiResult<T> PaymentRequired(string message = "Payment required")
        => Error(message, CRUDStatusCodeRes.PAYMENT_REQUIRED);        

    // ====================== Validation ======================

    public static ApiResult<T> ValidationError(
        Dictionary<string, List<string>> errors,
        string message = "Validation error")
        => new(CRUDStatusCodeRes.UNPROCESSABLE_ENTITY, false, message, default, errors);

    // ====================== Helpers ======================

    public bool HasError => !IsSuccess;

    /// <summary>Returns Data or throws if the result is an error.</summary>
    public T Unwrap()
        => IsSuccess && Data is not null
            ? Data
            : throw new InvalidOperationException($"ApiResult error [{Code}]: {Message}");

    /// <summary>Returns Data or a fallback value when the result is an error/null.</summary>
    public T? UnwrapOrDefault(T? fallback = default)
        => IsSuccess ? Data : fallback;

    public override string ToString() => $"[{Code}] {Message}";
}